import pathlib
import warnings

from markdown_it import MarkdownIt
from fancy_list_plugin import fancy_list_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.anchors import anchors_plugin

from jinja2 import Environment, FileSystemLoader
env = Environment(
    loader=FileSystemLoader('templates')
)

base_template = env.get_template("base.html")

md = (
    MarkdownIt()
    .use(front_matter_plugin)
    .use(footnote_plugin)
    .use(
        fancy_list_plugin, allow_ordinal=False
    )
    .use(anchors_plugin, permalink=True, max_level=4)
    .disable('image')
    .enable('table')
)

def switch_md_to_html(self, tokens, idx, options, env):
    url = tokens[idx].attrGet("href")
    if url.endswith(".md"):
        url = url.replace(".md", ".html")
    tokens[idx].attrSet("href", url)

    # pass token to default renderer.
    return self.renderToken(tokens, idx, options, env)

md.add_render_rule("link_open", switch_md_to_html)

def extract_title(md_tokens: list, maxsearch: int = 5):
    title = None

    for token in md_tokens[:maxsearch]:
        tokendict = token.as_dict()
        try:
            if tokendict['type'] == 'inline':
                poss_title = tokendict['children'][0]['content']
                if len(poss_title) > 1:
                    # found!
                    title = poss_title
                    break

        except KeyError:
            warnings.warn('in extract_title, expected token structure failed')

    if title is None:
        warnings.warn('in extract_title, token was not found')

    return title

def render(text):
    mdtokens = md.parse(text)
    title = extract_title(mdtokens)
    return base_template.render(title=title, body=md.render(text))

## To export the html to a file, uncomment the lines below:
# from pathlib import Path
# Path("output.html").write_text(html_text)

if __name__ == "__main__":
    import sys

    p = pathlib.Path(sys.argv[-1])
    out = pathlib.Path("site")
    if p.is_dir():
        for subpath in p.glob("**/*.md"):
            outpath = out / subpath.with_suffix(".html")
            if outpath.name == "README.html":
                outpath = outpath.with_name("index.html")
            outpath.parent.mkdir(parents=True, exist_ok=True)
            outpath.write_text(render(subpath.read_text()))
    else:
        outpath = out / p.with_suffix(".html")
        if outpath.name == "README.html":
            outpath = outpath.with_name("index.html")
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(render(p.read_text()))
