

from flask import render_template


class IndexPage:
    def __init__(self, current_app):
        self.title = "Index"
        self.template = "index.html"
        self.frag_shader_path = "static/glsl/indexBGShader.glsl"

        self.context = {
            "title": self.title,
        }

    def get_frag_shader(self):
        with open(self.frag_shader_path, 'r') as file:
            fragment_shader_str = file.read()

        return fragment_shader_str

    def display(self):
        self.context['fragment_shader_str'] = self.get_frag_shader()
        return render_template(self.template, **self.context)