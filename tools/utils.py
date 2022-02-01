
def add_or_update_section(path, section, contents):
    """This adds or updates a section within the markdown file. The section
       starts at the line that matches section and goes until another line that
       starts with the same number of hashes."""
    lines = path.read_text().split("\n")
    if section not in lines:
        path.write_text("\n".join(lines + ["", section] + contents))
        return
    start = lines.index(section)
    lines_before = lines[:start+1]
    end = start + 1
    hashes = section.split(" ", maxsplit=1)[0]
    section_prefix = hashes + " "
    while end < len(lines):
        if lines[end].startswith(section_prefix):
            break
        end += 1
    lines_after = lines[end:]

    path.write_text("\n".join(lines_before + contents + lines_after))

def remove_section(path, section):
    """This adds or updates a section within the markdown file. The section
       starts at the line that matches section and goes until another line that
       starts with the same number of hashes."""
    lines = path.read_text().split("\n")
    if section not in lines:
        return
    start = lines.index(section)
    lines_before = lines[:start]
    end = start + 1
    hashes = section.split(" ", maxsplit=1)[0]
    section_prefix = hashes + " "
    while end < len(lines):
        if lines[end].startswith(section_prefix):
            break
        end += 1
    lines_after = lines[end:]

    path.write_text("\n".join(lines_before + lines_after))