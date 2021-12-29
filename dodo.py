from tools.render import render
import pathlib

def render_and_write(subpath, outpath):
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(render(subpath.read_text()))

# todo: create import rcw task
# todo: create import bill task

out = pathlib.Path("site")
def task_render():
    for subpath in pathlib.Path(".").glob("**/*.md"):
        outpath = out / subpath.with_suffix(".html")
        if outpath.name == "README.html":
            outpath = outpath.with_name("index.html")
        yield {
            "name": outpath,
            "targets": [outpath],
            "actions": [(render_and_write, (subpath, outpath))],
            "file_dep": ["tools/render.py", subpath],
            "clean": True,
        }
