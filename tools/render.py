import pathlib

from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin

md = (
    MarkdownIt()
    .use(front_matter_plugin)
    .use(footnote_plugin)
    .disable('image')
    .enable('table')
)

def render(text):
    tokens = md.parse(text)
    return md.render(text)

## To export the html to a file, uncomment the lines below:
# from pathlib import Path
# Path("output.html").write_text(html_text)

if __name__ == "__main__":
    import sys
    p = pathlib.Path(sys.argv[-1])
    print(p)
    print(p.read_text())
    print(render(p.read_text()))
