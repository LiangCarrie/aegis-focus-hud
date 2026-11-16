"""Pure task state and storyline import; no GUI dependencies."""
import json
import math
import re
import time
from pathlib import Path

RANKS = [(0, '黄阶 · 见习'), (100, '黄阶 · 行动员'), (300, '黄阶 · 精锐'),
         (650, '玄阶 · 特勤'), (1200, '玄阶 · 指挥官'), (2200, '地阶 · 先锋'),
         (4000, '地阶 · 守望者'), (7000, '天阶 · 执行官'), (12000, '天阶 · 星域统领')]

def rank(points):
    return next(name for threshold, name in reversed(RANKS) if points >= threshold)

def load_story(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    if Path(path).suffix.lower() == '.json':
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get('missions'), list):
            raise ValueError('JSON must contain a missions array')
        title = str(data.get('title') or Path(path).stem)
        missions = data['missions']
    else:
        title_match = re.search(r'^# (.+)$', text, re.M)
        title = title_match[1] if title_match else Path(path).stem
        sections = re.split(r'^## +(.+)$', text, flags=re.M)
        missions = [{'title': sections[i].strip(), 'briefing': sections[i+1].strip()}
                    for i in range(1, len(sections), 2)]
    if not missions:
        raise ValueError('No missions found; use ## chapter headings in Markdown')
    normalized = []
    for i, m in enumerate(missions):
        if not isinstance(m, dict) or not isinstance(m.get('title'), str):
            raise ValueError(f'Mission {i+1} is missing a title string')
        normalized.append({'title': m['title'], 'briefing': str(m.get('briefing', '')),
                           'objective': str(m.get('objective', 'Complete your focus objective'))})
    return {'title': title, 'missions': normalized}

class Timer:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock = clock
        self.total = float(seconds)
        self.remaining = self.total
        self.deadline = None

    def start(self):
        if self.deadline is None:
            self.deadline = self.clock() + self.remaining

    def left(self):
        return max(0, self.deadline - self.clock()) if self.deadline is not None else self.remaining

    def pause(self):
        self.remaining = self.left()
        self.deadline = None

    def display(self):
        seconds = math.ceil(self.left())
        return f'{seconds // 60:02d}:{seconds % 60:02d}'

def reward(elapsed_seconds, difficulty):
    return int(max(0, elapsed_seconds) / 60 * {'轻度': 2, '标准': 3, '挑战': 4}[difficulty])

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
