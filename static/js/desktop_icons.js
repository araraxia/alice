/**
 * DesktopIcons - Win98-style desktop icons. Click selects, double-click or Enter opens.
 * @param {Object} actions - Maps each icon's data-opens value to a function that opens its window.
 */
class DesktopIcons {
    constructor(actions) {
        this.actions = actions;
        this.icons = document.querySelectorAll('.desktop-icon');

        this.icons.forEach(icon => {
            icon.addEventListener('click', () => this.select(icon));
            icon.addEventListener('dblclick', () => this.open(icon));
            icon.addEventListener('keydown', e => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.open(icon);
                }
            });
        });

        // Clicking anywhere other than an icon clears the selection
        document.addEventListener('click', e => {
            if (!e.target.closest('.desktop-icon')) this.select(null);
        });
    }

    select(icon) {
        this.icons.forEach(i => i.classList.toggle('selected', i === icon));
    }

    open(icon) {
        const action = this.actions[icon.dataset.opens];
        if (action) {
            action();
        } else {
            console.warn(`No action registered for desktop icon '${icon.dataset.opens}'`);
        }
    }
}

window.DesktopIcons = DesktopIcons;
