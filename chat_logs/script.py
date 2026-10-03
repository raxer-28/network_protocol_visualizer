import os
import glob

# Determine local gemini/antigravity storage path
user_home = os.path.expanduser("~")
possible_dirs = [
    os.path.join(user_home, ".gemini", "antigravity"),
    os.path.join(user_home, ".gemini", "antigravity-ide"),
    os.path.join(user_home, ".gemini", "antigravity-backup"),
    os.path.join(user_home, "AppData", "Roaming", "Antigravity IDE")
]

output_file = os.path.join(os.getcwd(), "antigravity_chats.txt")

found_data = False
with open(output_file, "w", encoding="utf-8") as out:
    out.write("=== ANTIGRAVITY CHAT HISTORY EXPORT ===\n\n")
    for d in possible_dirs:
        if os.path.exists(d):
            out.write(f"\n--- Scanning directory: {d} ---\n")
            for root, dirs, files in os.walk(d):
                for file in files:
                    if file.endswith(('.jsonl', '.md', '.txt', '.db', '.pb')):
                        filepath = os.path.join(root, file)
                        out.write(f"\n[File: {filepath}]\n")
                        try:
                            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                # Print snippet or full text depending on readability
                                out.write(content[:5000] + ("\n... [truncated]" if len(content) > 5000 else "") + "\n")
                                found_data = True
                        except Exception as e:
                            out.write(f"(Could not read binary/locked file: {e})\n")

if found_data:
    print(f"Chat data successfully exported to: {output_file}")
else:
    print("No readable chat files found in standard paths. Please check your hidden folders.")