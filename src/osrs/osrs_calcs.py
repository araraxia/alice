from dataclasses import dataclass
from flask import render_template, url_for


class OSRSCalcsHandler:
    def __init__(self, app):
        self.app = app
        self.log = app.logger
        self.context = {
            
        }
        
    def render_index(self):
        directory = [
            {'label': 'Creating Super Combat Potions', 'url': url_for('osrs.calc')},
        ]
        
        return render_template(
            template_name_or_list="osrs/calc.html",
            title="OSRS Calculators",
            **self.context,
        )        
    
    