"""Native SDK options: cached choices and queued game-thread actions only."""
from mods_base import ButtonOption, DropdownOption, NestedOption


class CharacterMenu:
    def __init__(self, controller, log):
        self.controller, self.log = controller, log
        self.rows, self.keys, self.owners = [], {}, {'Me': 'self'}
        self.busy = False
        self.group = DropdownOption('character_category', 'All', ['All'], display_name='Character category',
                                    on_change_anytime=self.change_group)
        self.page = DropdownOption('character_page', '1', ['1'], display_name='Character page',
                                   on_change_anytime=self.change_page)
        self.character = DropdownOption('character', 'Choose a character', ['Choose a character'],
                                       display_name='Character')
        self.target = DropdownOption('target_player', 'Me', ['Me'], display_name='Change appearance for')
        self.result = ButtonOption('current_status', display_name='Status: load into a map and enable the mod',
                                   on_press=lambda _: self.show_status())
        self.browser = NestedOption('browse_characters', [], display_name='Browse characters',
                                    description='Open a category, a page, then a character for Preview and Apply.')
        self.options = [
            ButtonOption('refresh_characters', display_name='Refresh characters and players',
                         on_press=lambda _: self.refresh()),
            self.target, self.browser,
            ButtonOption('restore_character', display_name='Restore selected player',
                         on_press=lambda _: self.action('restore')),
            ButtonOption('restore_everyone', display_name='Restore all changed players',
                         on_press=lambda _: self.action('restore_all')),
            ButtonOption('clear_previews', display_name='Remove character previews',
                         on_press=lambda _: self.action('clear')),
            self.result,
        ]

    def set_choices(self, option, choices):
        option.choices = choices
        if option.value not in choices:
            option.value = choices[0]

    def refresh(self):
        self.rows = self.controller.choices()
        self.busy = True
        try:
            self.set_choices(self.group, ['All', *sorted({r['group'] for r in self.rows})])
            self.owners = {'Me': 'self'}
            for row in self.controller.players:
                if row['key'] != 'self':
                    self.owners[f"{row['name']} [{row['key']}]"] = row['key']
            self.set_choices(self.target, list(self.owners))
            self.rebuild(self.group.value, self.page.value)
            self.build_browser()
        finally:
            self.busy = False
        self.show_status()

    def build_browser(self):
        categories = []
        for group_index, group in enumerate(sorted({r['group'] for r in self.rows})):
            rows = [r for r in self.rows if r['group'] == group]
            pages = []
            for start in range(0, len(rows), 25):
                characters = []
                for row in rows[start:start + 25]:
                    key = row['key']
                    label = row['name'] + (' (preview only)' if not row.get('apply_enabled', True) else '')
                    actions = [ButtonOption('preview', display_name='Preview this character',
                        on_press=lambda _, key=key: self.action('preview', key))]
                    if row.get('apply_enabled', True):
                        actions.append(ButtonOption('apply', display_name='Apply this character',
                            on_press=lambda _, key=key: self.action('apply', key)))
                    actions.append(self.result)
                    characters.append(NestedOption(key, actions, display_name=label,
                        description=f"{key}. Apply uses the player selected in Change appearance for."))
                pages.append(NestedOption(f'page_{start // 25 + 1}', characters,
                    display_name=f'{start + 1}-{min(start + 25, len(rows))}: {rows[start]["name"]}'))
            children = pages[0].children if len(pages) == 1 else pages
            categories.append(NestedOption(f'category_{group_index}', children, display_name=group))
        self.browser.children = categories or [ButtonOption('empty', display_name='Load a map and refresh characters')]

    def change_group(self, _option, value):
        if not self.busy:
            self.rebuild(value, '1')

    def change_page(self, _option, value):
        if not self.busy:
            self.rebuild(self.group.value, value)

    def rebuild(self, group, page):
        previous = self.busy
        self.busy = True
        try:
            rows = [r for r in self.rows if group == 'All' or r['group'] == group]
            pages = [str(i + 1) for i in range(max(1, (len(rows) + 24) // 25))]
            self.page.choices = pages
            self.page.value = page if page in pages else '1'
            start = (int(self.page.value) - 1) * 25
            self.keys = {f"{r['name']} [{r['key']}]" + (' (preview only)' if not r.get('apply_enabled', True) else ''): r['key']
                         for r in rows[start:start + 25]}
            self.set_choices(self.character, list(self.keys) or ['No characters available'])
        finally:
            self.busy = previous

    def show_status(self):
        self.update_status()
        self.log(str(self.controller.status))

    def update_status(self):
        message = str(self.controller.status)
        self.result.display_name = 'Status: ' + message
        self.result.description = message

    def action(self, action, key=None):
        key = self.keys.get(self.character.value, '') if key is None else key
        owner = self.owners.get(self.target.value)
        if action in ('apply', 'preview') and (not key or not any(r['key'] == key for r in self.controller.choices())):
            self.log('Refresh characters and choose a current character first.')
            return
        if action in ('apply', 'restore') and (owner is None or
                (owner != 'self' and not any(r['key'] == owner for r in self.controller.players))):
            self.log('That player left. Refresh players and select the target again.')
            return
        accepted = self.controller.request(action, model=key if action in ('apply', 'preview') else '',
                                           owner=owner or 'self')
        self.result.display_name = 'Status: ' + (f'{action} queued' if accepted else self.controller.status)
        self.log(self.result.display_name)
