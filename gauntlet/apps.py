# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
from pathlib import Path

from .video import registry

APP_JOURNEYS = {
    'live-deep': ('kilncast', 'hard_load'),
    'live-switch': ('kilncast', 'soft_nav'),
    'live-back': ('kilncast', 'back_forward'),
    'news-home-article': ('ledger', 'link_click'),
    'news-article-section': ('ledger', 'link_click'),
    'news-back': ('ledger', 'back_forward'),
    'travel-search-results': ('elsewhere', 'soft_nav'),
    'travel-filter': ('elsewhere', 'soft_nav'),
    'travel-item': ('elsewhere', 'link_click'),
    'travel-book': ('elsewhere', 'link_click'),
    'forum-thread': ('commonplot', 'soft_nav'),
    'forum-back': ('commonplot', 'back_forward'),
    'social-post': ('morrow', 'soft_nav'),
    'social-profile': ('morrow', 'soft_nav'),
    'social-back': ('morrow', 'back_forward'),
    'mail-folder': ('letterdesk', 'in_app_state'),
    'mail-message': ('letterdesk', 'in_app_state'),
}
APP_SIZES = {
    'kilncast': (360_000, 62_000, 920, 54_000, 110),
    'ledger': (220_000, 78_000, 1800, 46_000, 60),
    'elsewhere': (310_000, 62_000, 2700, 84_000, 72),
    'commonplot': (190_000, 45_000, 1800, 42_000, 90),
    'morrow': (340_000, 68_000, 2500, 65_000, 65),
    'letterdesk': (320_000, 58_000, 1600, 52_000, 100),
}
NAMES = ('Mina Holt', 'Ari Bell', 'Noor Vale', 'Jules Moss', 'Tess Linden', 'Sol Rowan', 'Eden Brook', 'Robin Ash', 'Kit Aster', 'Cleo Reed', 'Alex Fern', 'Ren Sage')
NOTES = (
    'The best ideas arrived when we left a little room for the unexpected. A small experiment, a new conversation, and a reason to try again tomorrow.',
    'We took the long way home and found something worth sharing. Here is what we noticed along the way, with a few practical notes for anyone following.',
    'A good place begins with the people who care for it. This week we visited the workshop, asked a few questions, and made time to listen.',
    'There is more to this story than a quick glance suggests. These are the details that stayed with us, from the first sketch to the final afternoon.',
)
HEADLINES = (
    ('A railway garden is bringing a neighbourhood together', 'City & community', 'garden'),
    ('The new energy co-op keeping its power close to home', 'Climate', 'solar'),
    ('A night train returns to the coast, one station at a time', 'Journeys', 'train'),
    ('Inside the workshop where yesterday becomes tomorrow', 'Culture', 'workshop'),
    ('What a quieter high street could look like', 'City & community', 'street'),
    ('The small library with a very big circle of readers', 'Culture', 'library'),
    ('Meet the people making space for urban orchards', 'Climate', 'garden'),
    ('A harbour town finds a new rhythm after the rain', 'Journeys', 'coast'),
)


def app_data(slug, count):
    if slug == 'kilncast':
        return {'channels': [{'id': str(i), 'name': ('Softclay Studio', 'Nightjar Works', 'Copper & Pine', 'The Print Table', 'Moss Circuit', 'Slow Stitch Club')[i%6] + (f' / room {i//6+1}' if i>=6 else ''),
            'title': ('A little clay, a lot of possibility', 'Carving a night sky from a block of wood', 'A lamp for the corner of the room', 'A fresh edition, pulled by hand', 'Building a tiny garden sensor', 'Mending the things we love')[i%6],
            'category': ('Ceramics', 'Printmaking', 'Woodworking', 'Printmaking', 'Creative tech', 'Textiles')[i%6], 'viewers': 238+i*37%4100,
            'description': NOTES[i%4], 'image': i%6, 'avatar': i%12,
            'schedule': [{'day': d, 'time': '18:30', 'topic': t} for d,t in zip(('Tuesday','Thursday','Sunday'),('Open studio','A new technique','Community make-along'))]} for i in range(24)],
            'chat': [{'id': i, 'author': NAMES[i%12], 'text': ('That glaze is catching the light beautifully.', 'Trying this with my own little bowl tonight!', 'A slower afternoon at the workbench. Perfect.', 'Could you show the handle join one more time?', 'The first cup of the day is always the best one.', 'Hello from the community print room.')[i%6], 'color': i%6} for i in range(count)]}
    if slug == 'ledger':
        return {'stories': [{'id': str(i), 'title': HEADLINES[i%8][0] + (f' · Dispatch {i//8+1}' if i>=8 else ''), 'section': HEADLINES[i%8][1], 'image': HEADLINES[i%8][2],
            'author': NAMES[i%12], 'minutes': 4+i%7, 'standfirst': NOTES[i%4],
            'paragraphs': [NOTES[(i+j)%4] + f' At the {("community hall", "station", "workshop", "harbour")[j%4]}, the conversation turned to {("shared space", "local knowledge", "a fresh start", "the next generation")[j%4]}. People brought their own experience, and the plans grew more useful for it.' for j in range(22)],
            'tags': ['People','Places','A changing city']} for i in range(count)]}
    if slug == 'elsewhere':
        return {'stays': [{'id':str(i), 'name': ('Juniper House', 'The Saltwater Rooms', 'Aster Courtyard', 'North Window Lodge', 'The Old Glasshouse', 'Willow Quay')[i%6] + (f' · Suite {i//6+1}' if i>=6 else ''),
            'place': ('Port Alder', 'Westhaven', 'Port Alder', 'Pine Reach', 'Westhaven', 'Port Alder')[i%6], 'type': ('Guesthouse','Coastal retreat','Boutique hotel','Forest lodge','Garden stay','Harbour inn')[i%6],
            'price': 126+i*17%170, 'rating': round(8.6+(i%14)/10,1), 'reviews': 128+i*37, 'image':i%12, 'breakfast':i%2==0,
            'description': ('Wake to the garden, wander down to the harbour, and come home to a table by the window. Thoughtful rooms, local breakfasts and a little more space to slow down. '+NOTES[i%4]),
            'amenities': ['Garden terrace','Breakfast available','Free cancellation','Wi-Fi','Walk to the water','Locally owned'],
            'rooms': [{'name':name,'beds':'1 queen bed','size':24+j*6,'price':126+i*17%170+j*28} for j,name in enumerate(('Garden room','Courtyard studio','Harbour suite'))],
            'reviewsList':[{'author':NAMES[j%12], 'text':NOTES[(i+j)%4], 'score':9+j%2} for j in range(14)]} for i in range(count)]}
    if slug == 'commonplot':
        return {'threads': [{'id':str(i),'title':('We turned an unused corner into a seed library. Here is what worked.', 'What is the one tool you keep reaching for?', 'A weekend walking map, drawn by the people who live here', 'Show us the smallest thing you made this week', 'How would you make this courtyard feel welcoming?', 'The monthly repair table is back this Saturday')[i%6] + (f' · Update {i//6+1}' if i>=6 else ''),
            'community':('Neighbourhood projects','Tools & making','Slow journeys','Small victories','Shared spaces','Repair together')[i%6], 'author':NAMES[i%12], 'votes':148+i*31%1800,'comments':36+i*7%180,
            'body':NOTES[i%4]+' We started with a borrowed table and a handwritten sign. Three weeks later, the neighbours had added their own shelves, labels and ideas. What would you try in your street?', 'image':i%4} for i in range(count)],
            'comments':[{'id':i,'parent': i-1 if i%5 else None, 'author':NAMES[i%12],'text':NOTES[i%4], 'votes':4+i*17%120} for i in range(100)]}
    if slug == 'morrow':
        return {'posts':[{'id':str(i),'author':NAMES[i%12], 'avatar':i%12,'place':('Port Alder','North Window Studio','The community garden','Along the coast')[i%4],
            'text':('A little room for something green. We spent the morning planting, then sat down to see who would stop by. Best part of the week.', 'The sketchbook came home a little heavier today. New lines, new colours, and a few notes from a very good walk.', 'Made with borrowed tools and plenty of tea. There is something lovely about learning alongside your neighbours.', 'Same path, different light. An afternoon reminder to keep looking.')[i%4],
            'image':i%8,'likes':48+i*19%500,'comments':[{'author':NAMES[(i+j+1)%12], 'text':NOTES[j%4]} for j in range(12)]} for i in range(count)],
            'profiles':[{'id':str(i),'name':NAMES[i], 'bio':'Making things, growing things, and finding a little wonder close to home.', 'followers':120+i*47,'interests':['Gardens','Making','Slow weekends']} for i in range(12)]}
    return {'folders': [{'id':name.lower(), 'name':name, 'count':number} for name,number in (('Inbox',24),('Starred',8),('Sent',32),('Archive',120))],
        'messages':[{'id':str(i),'folder': ('inbox','archive','sent','starred')[i%4], 'author':NAMES[i%12], 'email':NAMES[i%12].lower().replace(' ','.')+'@letters.gauntlet.test',
            'subject':('A few good things for next week','Your place at the long table','The garden plan is ready to share','Notes from the afternoon workshop','A small update from the coast','Shall we try Saturday?','The first print is ready','One more idea for the courtyard')[i%8],
            'preview':NOTES[i%4], 'time':f'{9+i%8}:{i*7%60:02}', 'unread':i%3==0,'starred':i%7==0,
            'body':[f'Hi Rowan,',NOTES[i%4],NOTES[(i+1)%4],'I have attached the outline so we can all add our ideas before Friday. There is no rush; a few notes in the margins would be lovely.',f'Thanks,\n{NAMES[i%12]}'],
            'attachment':i%3==0} for i in range(count*4)]}


def app_routes(recipes, origins):
    routes = {}
    root = Path(__file__).resolve().parents[1] / 'scenarios/apps'
    def add(path, value, mime='application/json', cache='no-store'):
        body = json.dumps(value,separators=(',',':')).encode() if mime=='application/json' else value
        routes[path]={'body':body,'type':mime,'cache':cache}
    for slug in APP_SIZES:
        recipe=recipes[slug]
        document=(root/slug/'index.html').read_bytes()
        for route in ('home','channel','section','article','search','results','stay','booking','feed','thread','post','profile','mail'):
            add(f'/apps/{slug}/{route}',document,'text/html; charset=utf-8', 'private, max-age=60' if slug == 'ledger' else 'no-store')
        add(f'/apps/{slug}/registry.js',registry(recipe.js_bytes,slug),'text/javascript','public, max-age=3600')
        add(f'/apps/{slug}/route-registry.js',registry(recipe.options['route_js_bytes'],slug+'Route'),'text/javascript','public, max-age=3600')
        css=''.join(f'.{slug}-tone-{i}{{border-color:hsl({i%360} 20% 82%);--card-tone:hsl({i%360} 20% 98%);--card-radius:{i%8+4}px;--card-space:{i%5+8}px}}\n' for i in range(recipe.css_rules))
        add(f'/apps/{slug}/route-work.js', registry(recipe.options['route_js_bytes'], slug+'View'), 'text/javascript', 'no-store')
        add(f'/apps/{slug}/components.css',css.encode(),'text/css','public, max-age=3600')
        content=app_data(slug,recipe.options['items'])
        for key,value in content.items():
            add(f'/apps/{slug}/data/{key}.json',value)
        primary=next(iter(content.values()))
        if slug!='letterdesk':
            for item in primary:
                if 'id' in item:
                    add(f'/apps/{slug}/data/item-{item["id"]}.json',item)
    add('/apps/video/route-work.js', registry(110*1024, 'videoView'), 'text/javascript', 'no-store')
    port=origins[0].rsplit(':',1)[1]
    add('/apps/ledger/ad',b'<!doctype html><html lang="en"><style>body{background:#e9ecdf;color:#3c5042;font:14px system-ui;padding:20px}small{letter-spacing:2px}h2{font:26px Georgia}</style><small>DAYBREAK PARTNER STUDIO</small><h2>Good ideas grow here.</h2><p>Local spaces. A little possibility.</p></html>','text/html')
    consent=f'window.ledgerConsent={{essential:true,optional:false,source:"https://ledger-consent.gauntlet.test:{port}"}};'
    add('/apps/ledger/consent.js',consent.encode(),'text/javascript')
    return routes
