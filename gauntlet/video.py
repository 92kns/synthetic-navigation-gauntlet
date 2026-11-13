# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
from pathlib import Path

TITLES = (
    ('The quiet side of the ridge', 'A morning above the clouds', 'Land & light'),
    ('Where the river takes its time', 'Following the water home', 'The long way home'),
    ('A cabin, a kettle, a little rain', 'A slower kind of weekend', 'Made by hand'),
    ('Last light on the salt marsh', 'The shape of the evening', 'Land & light'),
    ('Building a table for long conversations', 'From tree to table', 'Made by hand'),
    ('The coastal path nobody rushes', 'One more bend in the trail', 'The long way home'),
    ('Sketchbook pages from the high country', 'Lines in the landscape', 'Land & light'),
    ('An old bicycle and a new direction', 'Taking the small roads', 'The long way home'),
)
CHANNELS = ('Rowan & the Range', 'Slow Current Studio', 'The Timber Journal', 'Coastline Collective', 'Everyday Outside', 'North Window Films', 'Small Hours Workshop', 'The Wandering Line')
SCENES = ('Layered mountain ridges beneath a pale morning sky', 'A winding river through a wooded valley', 'A timber cabin on a misty hillside', 'Warm evening light over coastal hills')
DESCRIPTION = 'A small journey with room to look around. We followed the changing light, stopped for a cup of tea, and came home with a few stories worth sharing. Recorded on foot with a sketchbook and a patient eye. '


def catalogue(count):
    return [{
        'id': f'film-{index}', 'image': index % 24,
        'title': TITLES[index % len(TITLES)][0] + (f' · Field journal {index//8+1}' if index >= 8 else ''),
        'shortTitle': TITLES[index % len(TITLES)][1],
        'category': TITLES[index % len(TITLES)][2],
        'channel': CHANNELS[index % len(CHANNELS)],
        'scene': SCENES[index % len(SCENES)],
        'duration': f'{12+index%19}:{(index*17)%60:02}',
        'views': f'{32+index*13%240}K views', 'age': f'{1+index%12} days ago',
        'description': DESCRIPTION,
        'chapters': [{'time': f'{chapter*3}:00', 'title': f'{label} · notebook {index+1}'} for chapter,label in enumerate(('Setting out','A change of light','Along the trail','A place to pause','The way back'))],
    } for index in range(count)]


def registry(budget, prefix):
    parts = ['export const components = [\n']
    index = 0
    while sum(map(len, parts)) < budget:
        parts.append(f'function {prefix}{index}(props){{return {{name:"{prefix}-{index}",tone:props.tone||"field",density:props.density||"comfortable",caption:props.caption||"A view from the trail",duration:{index%1200},order:{index},enabled:props.enabled!==false}};}},\n')
        index += 1
    parts.append('];\nexport const schemas = components.map(component => component({tone:"natural"}));\n')
    return ''.join(parts).encode()


def video_routes(recipe):
    options = recipe.options
    videos = catalogue(options['catalogue'])
    routes = {}

    def add(path, data, mime='application/json', cache='no-store'):
        body = json.dumps(data, separators=(',', ':')).encode() if mime == 'application/json' else data
        routes[path] = {'body': body, 'type': mime, 'cache': cache}

    root = Path(__file__).resolve().parents[1] / 'scenarios/video'
    document = (root / 'index.html').read_bytes()
    add('/video/watch', document, 'text/html; charset=utf-8')
    add('/video/search', document, 'text/html; charset=utf-8')
    add('/video/registry.js', registry(recipe.js_bytes, 'component'), 'text/javascript', 'public, max-age=3600')
    add('/video/watch-registry.js', registry(options['watch_js_bytes'], 'watch'), 'text/javascript', 'public, max-age=3600')
    css = ''.join(f'.ff-tone-{index}{{border-color:hsl({index%360} 18% 68%);color:hsl({index%360} 22% 24%);border-radius:{index%12}px;letter-spacing:{index%3*.01:.2f}em}}\n' for index in range(recipe.css_rules))
    add('/video/components.css', css.encode(), 'text/css', 'public, max-age=3600')
    add('/video/data/search.json', {'videos': videos[:options['results']]})
    for number in range(options['routes']):
        video = videos[number]
        transcript = [{'time': f'{cue//60:02}:{cue%60:02}', 'text': f'{DESCRIPTION}Field observation {cue+1}: {video["shortTitle"].lower()}.'} for cue in range(options['transcript'])]
        related = [videos[(number+index+1)%options['routes']] for index in range(options['related'])]
        add(f'/video/data/film-{number}.json', {'video':video,'catalogue':videos})
        add(f'/video/data/related-film-{number}.json', {'related':related})
        add(f'/video/data/transcript-film-{number}.json', {'transcript':transcript})
        add(f'/video/data/channel-film-{number}.json', {'channel':{'name':video['channel'],'followers':'48.2K fellow wanderers','about':DESCRIPTION}})
        add(f'/video/data/playback-film-{number}.json', {'playback':{'duration':video['duration'],'chapters':video['chapters'],'preview':True}})
        add(f'/video/data/captions-film-{number}.json', {'captions':{'language':'English','available':True}})
        comments = []
        for index in range(options['comments']):
            comments.append({'author':f'{("Aster", "Linden", "Moss", "Juniper", "Sage", "River")[index%6]} {index+1}',
                'age':f'{index%7+1} days ago','likes':index*19%127,
                'text':f'The light at {index%12+1}:20 made me stop and look again. {DESCRIPTION}',
                'reply':{'author':video['channel'],'age':'1 day ago','likes':index%13,'text':'Thank you for wandering along with us. There is always something new to notice on a familiar path.'}})
        add(f'/video/data/comments-film-{number}.json', {'comments':comments})
    return routes
