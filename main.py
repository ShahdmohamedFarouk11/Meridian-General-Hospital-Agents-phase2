from mcp.server import MCPServer
import os
mcp = MCPServer("AI server")
notes = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.txt")
def ensure_file():
    if not os.path.exists(notes):
        with open(notes, "w") as f:
            f.write("")
@mcp.tool()
def add_note(note: str) -> str:
    """Add a note to the notes file."""
    ensure_file()
    with open(notes, "a") as f:
        f.write(note + "\n")
    return "Note added."
@mcp.tool()
def read_notes() -> str:
    """Read all notes from the notes file."""
    ensure_file()
    with open(notes, "r") as f:
        return f.read().strip() or "No notes found."
@mcp.tool()
def remove_note(note: str) -> str:
    """Remove a note from the notes file."""
    ensure_file()
    with open(notes, "r") as f:
        lines = f.readlines()
    with open(notes, "w") as f:
        for line in lines:
            if line.strip() != note.strip():
                f.write(line)
    return "Note removed."
@mcp.resource("notes://{path}")
def get_note_resource(path: str) -> str:
    """Get a note resource by path."""
    ensure_file()
    with open(notes, "r") as f:
        lines = f.readlines()
    for line in lines:
        if line.strip() == path.strip():
            return line.strip()
    return "Note not found."
@mcp.prompt()
def note_summary() -> str:
    """Summarize the notes."""
    ensure_file()
    with open(notes, "r") as f:
        lines = f.readlines()
    if not lines:
        return "No notes to summarize."
    summary = "Summary of notes:\n"
    for i, line in enumerate(lines, 1):
        summary += f"{i}. {line.strip()}\n"
    return summary.strip()