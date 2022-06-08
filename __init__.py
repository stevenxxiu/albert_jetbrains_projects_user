# -*- coding: utf-8 -*-

'''List and open JetBrains IDE projects.'''
import time
from pathlib import Path
from xml.etree import ElementTree

from albert import Item, ProcAction, iconLookup  # pylint: disable=import-error


__title__ = 'Jetbrains IDE Projects'
__version__ = '0.4.5'
__triggers__ = 'jb '
__authors__ = 'Markus Richter, Thomas Queste'

default_icon = str(Path(__file__).parent / 'icons/jetbrains.svg')

JETBRAINS_XDG_CONFIG_DIR = Path.home() / '.config/JetBrains'

# `[(app_name, icon_name, desktop_file)]`
IDE_CONFIGS = [
    ('CLion', 'clion', 'jetbrains-clion.desktop'),
    ('IntelliJIdea', 'idea', 'jetbrains-idea.desktop'),
    ('PyCharm', 'pycharm', 'pycharm-professional.desktop'),
]


def find_icons():
    return {app_name: iconLookup(icon_name) or default_icon for app_name, icon_name, desktop_file in IDE_CONFIGS}


def get_recent_projects(path):
    '''
    :param path: Parse the xml at `path`.
    :return: All recent project paths and the time they were last open.
    '''
    root = ElementTree.parse(path).getroot()  # type:ElementTree.Element
    add_info = None
    path2timestamp = {}
    for option_tag in root[0]:  # type:ElementTree.Element
        if option_tag.attrib['name'] == 'recentPaths':
            for recent_path in option_tag[0]:
                path2timestamp[recent_path.attrib['value']] = 0
        elif option_tag.attrib['name'] == 'additionalInfo':
            add_info = option_tag[0]

    # For all `additionalInfo` entries, also add the real timestamp
    if add_info is not None:
        for entry_tag in add_info:
            for option_tag in entry_tag[0][0]:
                if (
                    option_tag.tag == 'option'
                    and 'name' in option_tag.attrib
                    and option_tag.attrib['name'] == 'projectOpenTimestamp'
                ):
                    path2timestamp[entry_tag.attrib['key']] = int(option_tag.attrib['value'])

    return [(timestamp, path.replace('$USER_HOME$', str(Path.home()))) for path, timestamp in path2timestamp.items()]


def find_config_path(app_name: str):
    '''
    :param app_name:
    :return: The actual path to the relevant xml file, of the most recent configuration directory.
    '''
    xdg_dir = JETBRAINS_XDG_CONFIG_DIR
    if not xdg_dir.is_dir():
        return None

    # Dirs contains possibly multiple directories for a program, e.g.
    #
    # - `~/.config/JetBrains/PyCharm2021.3/`
    # - `~/.config/JetBrains/PyCharm2022.1/`
    dirs = [f for f in xdg_dir.iterdir() if (xdg_dir / f).is_dir() and f.name.startswith(app_name)]
    # Take the newest
    dirs.sort(reverse=True)
    if not dirs:
        return None
    return xdg_dir / dirs[0] / 'options/recentProjects.xml'


def handleQuery(query):
    if not query.isTriggered:
        return None
    desktop_files = {app_name: desktop_file for app_name, icon_name, desktop_file in IDE_CONFIGS}
    icons = find_icons()
    # `[(project_timestamp, project_path, app_name)]`
    projects = []

    for app_name, icon_name, _desktop_file in IDE_CONFIGS:
        full_config_path = find_config_path(app_name)
        if full_config_path is None:
            continue
        projects.extend([[e[0], e[1], app_name] for e in get_recent_projects(full_config_path)])

    # List all projects or the one corresponding to the query
    if query.string:
        projects = [p for p in projects if p[1].lower().find(query.string.lower()) != -1]

    # Disable automatic sorting
    query.disableSort()
    # Sort by last modified. Most recent first.
    projects.sort(key=lambda s: s[0], reverse=True)

    items = []
    now = int(time.time() * 1000.0)
    for last_update, project_path, app_name in projects:
        if not Path(project_path).exists():
            continue
        project_dir = Path(project_path).name
        desktop_file = desktop_files[app_name]
        if not desktop_file:
            continue

        output_entry = Item(
            id=f'{now - last_update:015d}-{project_path}-{app_name}',
            icon=icons[app_name],
            text=project_dir,
            subtext=project_path,
            completion=__triggers__ + project_dir,
            actions=[ProcAction(text=f'Open in {app_name}', commandline=['gtk-launch', desktop_file, project_path])],
        )
        items.append(output_entry)

    return items
