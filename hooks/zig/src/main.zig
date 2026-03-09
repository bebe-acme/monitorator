const std = @import("std");
const fs = std.fs;
const json = std.json;
const mem = std.mem;

// ── Constants ──────────────────────────────────────────────────────────

const max_stdin = 64 * 1024;
const max_file = 8 * 1024;
const max_path = 4096;
const truncate_len = 200;
const tool_input_val_max = 80;
const arena_size = 256 * 1024; // 256KB arena — fits all allocations

// ── Main ───────────────────────────────────────────────────────────────

pub fn main() void {
    // Single fixed-buffer arena — no system allocator calls, no cleanup needed
    var arena_buf: [arena_size]u8 = undefined;
    var fba = std.heap.FixedBufferAllocator.init(&arena_buf);
    const alloc = fba.allocator();
    run(alloc) catch {};
}

fn run(alloc: mem.Allocator) !void {
    // Read stdin into stack buffer
    var stdin_buf: [max_stdin]u8 = undefined;
    const stdin_len = readStdin(&stdin_buf);
    if (stdin_len == 0) return;

    const trimmed = mem.trim(u8, stdin_buf[0..stdin_len], &std.ascii.whitespace);
    if (trimmed.len == 0) return;

    // Parse event JSON
    const parsed_event = json.parseFromSlice(json.Value, alloc, trimmed, .{}) catch return;
    const event = parsed_event.value;
    if (event != .object) return;

    const event_type = getStr(event, "hook_event_name") orelse getStr(event, "type") orelse return;
    const session_id = getStr(event, "session_id") orelse return;
    const cwd = getStr(event, "cwd") orelse "";
    if (session_id.len == 0) return;

    // Resolve sessions directory
    var sessions_dir_buf: [max_path]u8 = undefined;
    const sessions_dir = getSessionsDir(&sessions_dir_buf) orelse return;

    // Read existing session file into stack buffer
    var existing_buf: [max_file]u8 = undefined;
    const existing_len = readSessionFile(&existing_buf, sessions_dir, session_id);
    const existing: ?json.Value = if (existing_len > 0) blk: {
        const p = json.parseFromSlice(json.Value, alloc, existing_buf[0..existing_len], .{}) catch break :blk null;
        break :blk p.value;
    } else null;

    // Build output state
    const now = nowTimestamp();
    var state = json.ObjectMap.init(alloc);

    try putStr(&state, "session_id", session_id);
    try putStr(&state, "cwd", if (cwd.len > 0) cwd else existingStr(existing, "cwd"));
    try putStr(&state, "project_name", existingStrOr(existing, "project_name", projectNameFromCwd(cwd)));
    try putStr(&state, "status", existingStrOr(existing, "status", "unknown"));
    try putStr(&state, "last_event", event_type);
    try putFloat(&state, "timestamp", existingFloat(existing, "timestamp") orelse now);
    try putFloat(&state, "updated_at", now);
    try putStrOrNull(&state, "git_branch", existingStrOpt(existing, "git_branch"));
    try putStrOrNull(&state, "last_tool", existingStrOpt(existing, "last_tool"));
    try putStrOrNull(&state, "last_tool_input_summary", existingStrOpt(existing, "last_tool_input_summary"));
    try putStrOrNull(&state, "last_prompt_summary", existingStrOpt(existing, "last_prompt_summary"));
    try putInt(&state, "subagent_count", existingInt(existing, "subagent_count"));
    try putStrOrNull(&state, "permission_mode", existingStrOpt(existing, "permission_mode"));

    // Detect git branch by reading .git/HEAD directly (no subprocess)
    const effective_cwd = getObjStr(state, "cwd");
    if (effective_cwd.len > 0) {
        var branch_buf: [256]u8 = undefined;
        if (detectGitBranch(effective_cwd, &branch_buf)) |branch| {
            try putStr(&state, "git_branch", branch);
        }
    }

    // Apply event-specific state changes
    if (mem.eql(u8, event_type, "SessionStart")) {
        try putStr(&state, "status", "idle");
        try putFloat(&state, "timestamp", now);
        try putStr(&state, "project_name", projectNameFromCwd(cwd));
    } else if (mem.eql(u8, event_type, "UserPromptSubmit")) {
        try putStr(&state, "status", "thinking");
        const prompt = getStr(event, "prompt") orelse "";
        if (prompt.len > 0 and !isSystemMessage(prompt)) {
            try putStr(&state, "last_prompt_summary", truncateStr(prompt));
        }
    } else if (mem.eql(u8, event_type, "PreToolUse")) {
        try putStr(&state, "status", "executing");
        if (getStr(event, "tool_name")) |tool_name| {
            try putStr(&state, "last_tool", tool_name);
        }
        if (getVal(event, "tool_input")) |tool_input| {
            const summary = summarizeToolInput(alloc, tool_input) catch "";
            if (summary.len > 0) {
                try putStr(&state, "last_tool_input_summary", summary);
            }
        }
    } else if (mem.eql(u8, event_type, "PostToolUse")) {
        try putStr(&state, "status", "thinking");
    } else if (mem.eql(u8, event_type, "Stop") or mem.eql(u8, event_type, "SessionEnd")) {
        try putStr(&state, "status", "terminated");
    } else if (mem.eql(u8, event_type, "Notification")) {
        const notification_type = getStr(event, "notification_type") orelse "";
        const message = getStr(event, "message") orelse "";
        if (mem.eql(u8, notification_type, "permission_prompt") or containsLower(message, "permission")) {
            try putStr(&state, "status", "waiting_permission");
        }
    } else if (mem.eql(u8, event_type, "SubagentStart")) {
        const count = existingInt(existing, "subagent_count") + 1;
        try putInt(&state, "subagent_count", count);
        try putStr(&state, "status", "subagent_running");
    } else if (mem.eql(u8, event_type, "SubagentStop")) {
        const raw = existingInt(existing, "subagent_count") - 1;
        const count = if (raw < 0) @as(i64, 0) else raw;
        try putInt(&state, "subagent_count", count);
        if (count > 0) {
            try putStr(&state, "status", "subagent_running");
        } else {
            try putStr(&state, "status", "thinking");
        }
    }

    // Serialize and write atomically
    const output = json.Stringify.valueAlloc(alloc, json.Value{ .object = state }, .{}) catch return;

    atomicWrite(sessions_dir, session_id, output) catch return;
}

// ── stdin ──────────────────────────────────────────────────────────────

fn readStdin(buf: *[max_stdin]u8) usize {
    const file = fs.File.stdin();
    var total: usize = 0;
    while (total < max_stdin) {
        const n = file.read(buf[total..]) catch break;
        if (n == 0) break;
        total += n;
    }
    return total;
}

// ── Sessions directory ─────────────────────────────────────────────────

fn getSessionsDir(buf: *[max_path]u8) ?[]const u8 {
    if (std.posix.getenv("MONITORATOR_SESSIONS_DIR")) |override| {
        if (override.len > 0 and override.len < max_path) {
            @memcpy(buf[0..override.len], override);
            return buf[0..override.len];
        }
    }
    if (std.posix.getenv("HOME")) |home| {
        const suffix = "/.monitorator/sessions";
        if (home.len + suffix.len < max_path) {
            @memcpy(buf[0..home.len], home);
            @memcpy(buf[home.len..][0..suffix.len], suffix);
            return buf[0 .. home.len + suffix.len];
        }
    }
    return null;
}

// ── File I/O ───────────────────────────────────────────────────────────

fn readSessionFile(buf: *[max_file]u8, sessions_dir: []const u8, session_id: []const u8) usize {
    var path_buf: [max_path]u8 = undefined;
    const path = buildPath(&path_buf, sessions_dir, session_id, ".json") orelse return 0;

    const file = fs.openFileAbsolute(path, .{}) catch return 0;
    defer file.close();

    var total: usize = 0;
    while (total < max_file) {
        const n = file.read(buf[total..]) catch break;
        if (n == 0) break;
        total += n;
    }
    return total;
}

fn atomicWrite(sessions_dir: []const u8, session_id: []const u8, data: []const u8) !void {
    // Ensure directory exists
    fs.makeDirAbsolute(sessions_dir) catch |err| switch (err) {
        error.PathAlreadyExists => {},
        else => {
            ensureParentDirs(sessions_dir) catch return err;
            fs.makeDirAbsolute(sessions_dir) catch |e| switch (e) {
                error.PathAlreadyExists => {},
                else => return e,
            };
        },
    };

    var target_buf: [max_path]u8 = undefined;
    const target_path = buildPath(&target_buf, sessions_dir, session_id, ".json") orelse return error.PathTooLong;

    var tmp_buf: [max_path]u8 = undefined;
    const tmp_path = buildPath(&tmp_buf, sessions_dir, session_id, ".tmp") orelse return error.PathTooLong;

    const tmp_file = fs.createFileAbsolute(tmp_path, .{}) catch return error.WriteFailed;
    tmp_file.writeAll(data) catch {
        tmp_file.close();
        fs.deleteFileAbsolute(tmp_path) catch {};
        return error.WriteFailed;
    };
    tmp_file.close();

    fs.renameAbsolute(tmp_path, target_path) catch {
        fs.deleteFileAbsolute(tmp_path) catch {};
        return error.RenameFailed;
    };
}

fn ensureParentDirs(path: []const u8) !void {
    var i: usize = 1;
    while (i < path.len) : (i += 1) {
        if (path[i] == '/') {
            fs.makeDirAbsolute(path[0..i]) catch |err| switch (err) {
                error.PathAlreadyExists => {},
                else => return err,
            };
        }
    }
}

fn buildPath(buf: *[max_path]u8, dir: []const u8, name: []const u8, ext: []const u8) ?[]const u8 {
    const total = dir.len + 1 + name.len + ext.len;
    if (total >= max_path) return null;
    @memcpy(buf[0..dir.len], dir);
    buf[dir.len] = '/';
    @memcpy(buf[dir.len + 1 ..][0..name.len], name);
    @memcpy(buf[dir.len + 1 + name.len ..][0..ext.len], ext);
    return buf[0..total];
}

// ── Git branch detection ───────────────────────────────────────────────

fn detectGitBranch(cwd: []const u8, out_buf: *[256]u8) ?[]const u8 {
    var current_buf: [max_path]u8 = undefined;
    if (cwd.len >= max_path) return null;
    @memcpy(current_buf[0..cwd.len], cwd);
    var current_len = cwd.len;

    while (current_len > 0) {
        if (readGitHead(current_buf[0..current_len], out_buf)) |branch| {
            return branch;
        }
        current_len = lastSlash(current_buf[0..current_len]) orelse break;
    }
    return null;
}

fn readGitHead(dir: []const u8, out_buf: *[256]u8) ?[]const u8 {
    var path_buf: [max_path]u8 = undefined;
    const suffix = "/.git/HEAD";
    if (dir.len + suffix.len >= max_path) return null;
    @memcpy(path_buf[0..dir.len], dir);
    @memcpy(path_buf[dir.len..][0..suffix.len], suffix);

    const file = fs.openFileAbsolute(path_buf[0 .. dir.len + suffix.len], .{}) catch return null;
    defer file.close();

    var buf: [256]u8 = undefined;
    const n = file.read(&buf) catch return null;
    const content = mem.trim(u8, buf[0..n], &std.ascii.whitespace);

    const prefix = "ref: refs/heads/";
    if (mem.startsWith(u8, content, prefix)) {
        const branch = content[prefix.len..];
        if (branch.len > 0 and branch.len <= 256) {
            @memcpy(out_buf[0..branch.len], branch);
            return out_buf[0..branch.len];
        }
    }
    return null;
}

fn lastSlash(path: []const u8) ?usize {
    if (path.len <= 1) return null;
    var i = path.len - 1;
    while (i > 0) : (i -= 1) {
        if (path[i] == '/') return i;
    }
    return null;
}

// ── JSON helpers ───────────────────────────────────────────────────────

fn getStr(val: json.Value, key: []const u8) ?[]const u8 {
    if (val != .object) return null;
    const v = val.object.get(key) orelse return null;
    return switch (v) {
        .string => |s| s,
        else => null,
    };
}

fn getVal(val: json.Value, key: []const u8) ?json.Value {
    if (val != .object) return null;
    return val.object.get(key);
}

fn getObjStr(obj: json.ObjectMap, key: []const u8) []const u8 {
    const v = obj.get(key) orelse return "";
    return switch (v) {
        .string => |s| s,
        else => "",
    };
}

fn existingStr(existing: ?json.Value, key: []const u8) []const u8 {
    return getStr(existing orelse return "", key) orelse "";
}

fn existingStrOr(existing: ?json.Value, key: []const u8, default: []const u8) []const u8 {
    const s = getStr(existing orelse return default, key) orelse return default;
    return if (s.len == 0) default else s;
}

fn existingStrOpt(existing: ?json.Value, key: []const u8) ?[]const u8 {
    return getStr(existing orelse return null, key);
}

fn existingFloat(existing: ?json.Value, key: []const u8) ?f64 {
    const ex = existing orelse return null;
    if (ex != .object) return null;
    const v = ex.object.get(key) orelse return null;
    return switch (v) {
        .float => |f| f,
        .integer => |i| @floatFromInt(i),
        else => null,
    };
}

fn existingInt(existing: ?json.Value, key: []const u8) i64 {
    const ex = existing orelse return 0;
    if (ex != .object) return 0;
    const v = ex.object.get(key) orelse return 0;
    return switch (v) {
        .integer => |i| i,
        .float => |f| @intFromFloat(f),
        else => 0,
    };
}

fn putStr(obj: *json.ObjectMap, key: []const u8, val: []const u8) !void {
    try obj.put(key, .{ .string = val });
}

fn putStrOrNull(obj: *json.ObjectMap, key: []const u8, val: ?[]const u8) !void {
    if (val) |v| {
        try obj.put(key, .{ .string = v });
    } else {
        try obj.put(key, .null);
    }
}

fn putFloat(obj: *json.ObjectMap, key: []const u8, val: f64) !void {
    try obj.put(key, .{ .float = val });
}

fn putInt(obj: *json.ObjectMap, key: []const u8, val: i64) !void {
    try obj.put(key, .{ .integer = val });
}

// ── String utilities ───────────────────────────────────────────────────

fn projectNameFromCwd(cwd: []const u8) []const u8 {
    if (cwd.len == 0) return "unknown";
    var s = cwd;
    while (s.len > 0 and s[s.len - 1] == '/') s = s[0 .. s.len - 1];
    return if (mem.lastIndexOfScalar(u8, s, '/')) |idx| s[idx + 1 ..] else s;
}

fn truncateStr(text: []const u8) []const u8 {
    return if (text.len <= truncate_len) text else text[0..truncate_len];
}

fn isSystemMessage(text: []const u8) bool {
    const t = mem.trimLeft(u8, text, &std.ascii.whitespace);
    return t.len >= 2 and t[0] == '<' and std.ascii.isAlphabetic(t[1]);
}

fn containsLower(haystack: []const u8, needle: []const u8) bool {
    if (needle.len == 0) return true;
    if (haystack.len < needle.len) return false;
    var i: usize = 0;
    while (i + needle.len <= haystack.len) : (i += 1) {
        var match = true;
        for (0..needle.len) |j| {
            if (std.ascii.toLower(haystack[i + j]) != std.ascii.toLower(needle[j])) {
                match = false;
                break;
            }
        }
        if (match) return true;
    }
    return false;
}

fn summarizeToolInput(alloc: mem.Allocator, val: json.Value) ![]const u8 {
    if (val != .object) return "";

    var parts: std.ArrayList(u8) = .empty;
    var first = true;
    var it = val.object.iterator();
    while (it.next()) |entry| {
        if (!first) try parts.appendSlice(alloc, ", ");
        first = false;
        try parts.appendSlice(alloc, entry.key_ptr.*);
        try parts.appendSlice(alloc, ": ");

        switch (entry.value_ptr.*) {
            .string => |s| {
                const slice = if (s.len > tool_input_val_max) s[0..tool_input_val_max] else s;
                try parts.appendSlice(alloc, slice);
                if (s.len > tool_input_val_max) try parts.appendSlice(alloc, "...");
            },
            else => {
                const val_str = json.Stringify.valueAlloc(alloc, entry.value_ptr.*, .{}) catch "";
                const slice = if (val_str.len > tool_input_val_max) val_str[0..tool_input_val_max] else val_str;
                try parts.appendSlice(alloc, slice);
                if (val_str.len > tool_input_val_max) try parts.appendSlice(alloc, "...");
            },
        }
    }
    const result = parts.items; // no toOwnedSlice — arena owns everything
    return if (result.len > truncate_len) result[0..truncate_len] else result;
}

fn nowTimestamp() f64 {
    return @as(f64, @floatFromInt(std.time.nanoTimestamp())) / 1_000_000_000.0;
}
