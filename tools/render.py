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

def extract_title(text: str, path_debug=None, maxlines: int = 3, maxsearch: int = 6):

    # extract top N lines
    textlines = text.splitlines(keepends=True)
    top_n_lines = ''.join(textlines[:maxlines])

    # parse top N lines only for title (speeds up parsing considerably)
    md_tokens = md.parse(top_n_lines)

    # start title search in tokens
    is_h1 = False
    for token in md_tokens[:maxsearch]:
        tokendict = token.as_dict()

        # h1 text content expected in an h1 inline token with children type 'text'
        try:
            # detect h1 open
            if tokendict['type'] == 'heading_open' and tokendict['tag'] == 'h1':
                is_h1 = True
                continue

            # next loop there expect the inline token
            elif is_h1 and tokendict['type'] == 'inline' and 'children' in tokendict:
                # look in all children for h1 content
                for tokenchild in tokendict['children']:
                    if tokenchild['type'] == 'text':
                        poss_title = tokenchild['content']
                        if len(poss_title) > 1:
                            return poss_title

            else:
                is_h1 = False

        except KeyError:
            warnings.warn('in extract_title, expected token structure failed')

    # all tokens exhausted, not found
    warningmsg = 'title h1 token was not found'
    if path_debug is not None:
        warningmsg = warningmsg + ' for: ' + str(path_debug)
    warnings.warn(warningmsg)
    return None

def render(text, path_debug=None):
    title = extract_title(text, path_debug=path_debug)
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
            outpath.write_text(render(subpath.read_text(), path_debug=subpath))
    else:
        outpath = out / p.with_suffix(".html")
        if outpath.name == "README.html":
            outpath = outpath.with_name("index.html")
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(render(p.read_text()))
