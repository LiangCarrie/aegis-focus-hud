"""FOCUS // FIELD — Windows transparent focus overlay, AEGIS layered visor."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import winsound
from core import Timer, load_story, rank as original_rank, reward as original_reward, save_json, RANKS
from english_ui import translate, migrate_settings
from localization import DisplayVar, localize

def rank(points): return translate(original_rank(points))
def reward(seconds, difficulty):
    return original_reward(seconds, {"Light":"轻度", "Standard":"标准", "Challenge":"挑战"}.get(difficulty, difficulty))
from hud_renderer import VisorRenderer, HUDConfig, HUDState
from layered_window import LayeredSurface
from reticles import STYLES as ORIGINAL_STYLES, render_reticle
STYLES = {translate(name): value for name, value in ORIGINAL_STYLES.items()}
from hud_renderer import PALETTES
from PIL import Image, ImageTk

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data' / 'profile.json'
COLORS = {'Green · Routine': '#64efba', 'Blue · Active': '#68ceff', 'Yellow · Urgent': '#ffcf66', 'Red · Critical': '#ff7185'}
BG = '#0a111c'
PANEL = '#111e2d'
FG = '#dbe8f6'
KEY = '#010203'
user32 = ctypes.windll.user32
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
get_style = user32.GetWindowLongPtrW
get_style.argtypes = [wintypes.HWND, ctypes.c_int]
get_style.restype = ctypes.c_ssize_t
set_style = user32.SetWindowLongPtrW
set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
set_style.restype = ctypes.c_ssize_t

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('FOCUS // FIELD · Focus Mission Console')
        self.root.geometry('760x850')
        self.root.minsize(740, 650)
        self.root.configure(bg=BG)
        self.profile = {'points': 0, 'history': [], 'progress': {}, 'settings': {}}
        self.load_warning = ''
        if DATA.exists():
            try:
                saved = json.loads(DATA.read_text(encoding='utf-8'))
                if (not isinstance(saved, dict) or not isinstance(saved.get('points'), int)
                    or saved['points'] < 0 or not isinstance(saved.get('history'), list)
                    or not isinstance(saved.get('progress'), dict)):
                    raise ValueError('Invalid profile structure')
                self.profile.update(saved)
            except (OSError, ValueError, TypeError) as e:
                backup = DATA.with_name(f'profile-damaged-{int(time.time())}.json')
                DATA.rename(backup)
                self.load_warning = f'Unreadable profile; backup saved as {backup.name}：{e}'
        self.timer = None
        self.active = None
        self.awaiting = False
        self.visible = False
        self.stories = {}
        self.sound_path = None
        self.settings = self.profile.get('settings', {})
        if not isinstance(self.settings, dict): self.settings = {}
        self.settings = migrate_settings(self.settings)
        self.language = self.settings.get('language', 'zh')
        if self.language not in ('zh','en'): self.language='zh'
        self.display_vars=[]
        self.localized_widgets=[]
        self.language_choice=tk.StringVar(value='中文' if self.language=='zh' else 'English')
        self.color = DisplayVar(self,value=self.settings.get('color', 'Blue · Active'))
        if self.color.get() not in COLORS: self.color.set('Blue · Active')
        self.noise = DisplayVar(self,value=self.settings.get('noise', 'High'))
        self.cover = DisplayVar(self,value=self.settings.get('cover', 'Deep'))
        self.cross = tk.BooleanVar(value=self.settings.get('cross', True))
        style=self.settings.get('reticle_style','Precision Cross')
        self.reticle_style=DisplayVar(self,value=style if style in STYLES else 'Precision Cross')
        self.reticle_size=tk.DoubleVar(value=max(60,min(160,float(self.settings.get('reticle_size',100)))))
        self.reticle_motion=tk.BooleanVar(value=self.settings.get('reticle_motion',False))
        self.motion = tk.BooleanVar(value=self.settings.get('motion', True))
        self.brightness = tk.DoubleVar(value=self.settings.get('brightness', 92))
        self.boot_started = time.monotonic() - 10
        self.last_frame_time = 0
        self.last_render_ms = 0
        self.render_fault = False
        self.minutes = tk.StringVar(value='25')
        self.difficulty = DisplayVar(self,value='Standard')
        self.goal = tk.StringVar(value=self.tr('Complete your most important task'))
        self.story = DisplayVar(self,value='Free mission')
        self.chapter = tk.StringVar()
        self.sound = DisplayVar(self,value='Muted')
        self.status = DisplayVar(self,value='System ready / Awaiting mission',fragments=True)
        self.clock_text = tk.StringVar(value='25:00')
        self.build_ui()
        self.capture_labels()
        self.build_overlay()
        self.reload_stories()
        self.refresh_audio()
        self.hotkeys = []
        self.hotkey_events = queue.Queue()
        self.hotkey_stop = threading.Event()
        self.hotkey_thread = threading.Thread(target=self.listen_hotkeys, daemon=True)
        self.hotkey_thread.start()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.tick)
        self.restore_session()
        if self.load_warning: self.dialog("showwarning", 'Profile recovery', self.load_warning)

    def tr(self,text):
        return localize(str(text),self.language)

    def dialog(self,kind,title,body):
        return getattr(messagebox,kind)(self.tr(title),self.tr(body))

    def story_folder(self):
        folder=BASE / 'storylines'
        if self.language=='en': folder=folder / 'en'
        folder.mkdir(parents=True,exist_ok=True)
        return folder

    def capture_labels(self):
        self.static_labels=[]
        dynamic=(self.rank_label,self.reticle_size_label,self.hotkey_label)
        def visit(widget):
            if widget not in dynamic and 'text' in widget.keys() and not ('textvariable' in widget.keys() and widget.cget('textvariable')):
                original=widget.cget('text')
                if original:self.static_labels.append((widget,original))
            for child in widget.winfo_children():visit(child)
        visit(self.root)
        self.apply_labels()

    def apply_labels(self):
        self.root.title('FOCUS // FIELD · '+self.tr('Focus Mission Console'))
        for widget,original in self.static_labels:widget.configure(text=self.tr(original))
        self.update_rank()
        self.update_reticle_preview()

    def change_language(self,event=None):
        target='zh' if self.language_choice.get()=='中文' else 'en'
        if target==self.language:return
        selected=self.selected_mission()
        # Resolve displayed dropdown values before changing the translation table.
        for variable in self.display_vars:variable.get()
        old_default=self.tr('Complete your most important task')
        self.language=target
        for variable in self.display_vars:variable.refresh()
        for widget,values in self.localized_widgets:
            if widget not in (self.story_box,self.audio_box):widget['values']=[self.tr(v) for v in values]
        if self.goal.get()==old_default:self.goal.set(self.tr('Complete your most important task'))
        self.apply_labels()
        self.reload_stories()
        if selected:
            filename,index,_=selected
            for title,(name,story) in self.stories.items():
                if name==filename:
                    self.story.set(title);self.select_story()
                    self.chapter_box.current(min(index,len(story['missions'])-1));self.show_briefing()
                    break
        self.refresh_audio()
        if hasattr(self,'hotkey_descriptions'):
            self.hotkey_label.configure(text=self.tr('\n'.join(self.hotkey_descriptions)))
        self.persist()

    def build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=FG, font=('Microsoft YaHei UI', 10))
        style.configure('TCombobox', fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
        style.map('TCombobox', fieldbackground=[('readonly', PANEL)], foreground=[('readonly', FG)])
        style.configure('TButton', background=PANEL, foreground=FG, padding=9)
        style.map('TButton', background=[('active', '#234159')])
        style.configure('TCheckbutton', background=BG, foreground=FG)
        outer = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.root, command=outer.yview)
        outer.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); outer.pack(fill='both', expand=True)
        body = tk.Frame(outer, bg=BG, padx=26, pady=22)
        window = outer.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', lambda e: outer.configure(scrollregion=outer.bbox('all')))
        outer.bind('<Configure>', lambda e: outer.itemconfigure(window, width=e.width))
        self.root.bind('<MouseWheel>', lambda e: outer.yview_scroll(-int(e.delta/120), 'units') if not isinstance(e.widget, (tk.Text, ttk.Combobox)) else None)
        def label(text, size=10, color=FG):
            tk.Label(body, text=text, bg=BG, fg=color, font=('Microsoft YaHei UI', size), anchor='w').pack(fill='x', pady=(5, 3))
        label('F O C U S  / /  F I E L D', 23, '#68ceff')
        language_row=tk.Frame(body,bg=BG);language_row.pack(fill='x',pady=5)
        language_box=self.combo(language_row,'语言 / Language',self.language_choice,['中文','English'])
        language_box.bind('<<ComboboxSelected>>',self.change_language)
        label('YOUR SCREEN. YOUR MISSION. / PERSONAL FOCUS SYSTEM', 9, '#7893ac')
        self.rank_label = tk.Label(body, bg=BG, fg='#64efba', anchor='w')
        self.rank_label.pack(fill='x', pady=(12, 8)); self.update_rank()
        timer_row = tk.Frame(body, bg=PANEL); timer_row.pack(fill='x', pady=8)
        tk.Label(timer_row, textvariable=self.clock_text, bg=PANEL, fg=FG, font=('Consolas', 42)).pack(side='left', padx=16)
        tk.Label(timer_row, textvariable=self.status, bg=PANEL, fg='#91a9bf', wraplength=280, justify='left').pack(side='left', padx=10)
        label('01 / MISSION OBJECTIVE', 11)
        tk.Entry(body, textvariable=self.goal, bg=PANEL, fg=FG, insertbackground=FG, relief='flat', font=('Microsoft YaHei UI', 12)).pack(fill='x', ipady=10)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=10)
        self.combo(row, 'Focus minutes / Enter 1–240', self.minutes, ['15', '25', '45', '50', '60', '90'], False)
        self.combo(row, 'Difficulty', self.difficulty, ['Light', 'Standard', 'Challenge'])
        label('02 / STORY ARCHIVE', 11)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=5)
        self.story_box = self.combo(row, 'Storyline', self.story, ['Free mission'])
        self.chapter_box = self.combo(row, 'Chapter / Replay available', self.chapter, [])
        self.story_box.bind('<<ComboboxSelected>>', self.select_story)
        self.chapter_box.bind('<<ComboboxSelected>>', self.show_briefing)
        self.brief = tk.Text(body, height=5, wrap='word', bg=PANEL, fg='#adc4d7', relief='flat', padx=12, pady=10, font=('Microsoft YaHei UI', 10))
        self.brief.pack(fill='x')
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=6)
        ttk.Button(row, text='Open story folder', command=lambda: os.startfile(str(self.story_folder()))).pack(side='left')
        ttk.Button(row, text='Reload stories & audio', command=self.refresh_files).pack(side='left', padx=8)
        label('03 / AEGIS MK.IV TACTICAL VISOR', 11)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=5)
        ttk.Button(row, text='Full tactical preview', command=self.full_preview).pack(side='left')
        ttk.Button(row, text='Stealth preview', command=self.light_preview).pack(side='left', padx=6)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=5)
        self.combo(row, 'Alert palette', self.color, list(COLORS))
        self.combo(row, 'Visual noise', self.noise, ['Low', 'Medium', 'High'])
        self.combo(row, 'Edge coverage', self.cover, ['Light', 'Deep'])
        ttk.Checkbutton(body, text='Center reticle · Visual anchor', variable=self.cross).pack(anchor='w', pady=8)
        row=tk.Frame(body,bg=BG);row.pack(fill='x',pady=5)
        self.combo(row,'Reticle style',self.reticle_style,list(STYLES))
        self.reticle_preview=tk.Label(row,bg=PANEL,width=88,height=88)
        self.reticle_preview.pack(side='right',padx=6)
        row=tk.Frame(body,bg=BG);row.pack(fill='x',pady=4)
        self.reticle_size_label=tk.Label(row,text='Reticle size 100%',bg=BG,fg='#7893ac')
        self.reticle_size_label.pack(side='left')
        ttk.Scale(row,from_=60,to=160,variable=self.reticle_size).pack(side='left',fill='x',expand=True,padx=12)
        ttk.Checkbutton(body,text='Reticle motion · Ring/orbit edges only; center stays fixed',variable=self.reticle_motion).pack(anchor='w',pady=4)
        for variable in [self.reticle_style,self.reticle_size,self.color,self.cross]:
            variable.trace_add('write',self.update_reticle_preview)
        self.update_reticle_preview()
        ttk.Checkbutton(body, text='Animated instruments · Turn off to freeze animations', variable=self.motion).pack(anchor='w', pady=4)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=6)
        tk.Label(row, text='Visor brightness', bg=BG, fg='#7893ac').pack(side='left')
        ttk.Scale(row, from_=35, to=100, variable=self.brightness).pack(side='left', fill='x', expand=True, padx=12)
        row = tk.Frame(body, bg=BG); row.pack(fill='x')
        self.audio_box = self.combo(row, 'Local WAV soundscape / Loop playback', self.sound, ['Muted'])
        self.audio_box.bind('<<ComboboxSelected>>', lambda e: self.play_audio())
        label('04 / MISSION CONTROL', 11)
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=7)
        for i, (title, action) in enumerate([('Start mission', self.start), ('Pause / Resume', self.pause), ('Extract', self.finish), ('Abort', self.abort)]):
            row.columnconfigure(i, weight=1, uniform='actions')
            ttk.Button(row, text=title, command=action, width=8).grid(row=0, column=i, sticky='ew', padx=(0, 5))
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=5)
        ttk.Button(row, text='Show / Hide HUD', command=self.toggle).pack(side='left')
        ttk.Button(row, text='5-min break', command=lambda: self.start_break(5)).pack(side='left', padx=5)
        ttk.Button(row, text='15-min break', command=lambda: self.start_break(15)).pack(side='left')
        self.hotkey_label = tk.Label(body, text='Registering global hotkeys…', bg=BG, fg='#7893ac', anchor='w', justify='left', font=('Microsoft YaHei UI', 9))
        self.hotkey_label.pack(fill='x', pady=5)
        label('Clear center · Click-through · Primary display · Independent color & intensity', 9, '#7893ac')

    def combo(self, parent, title, variable, values, readonly=True):
        frame = tk.Frame(parent, bg=BG); frame.pack(side='left', fill='x', expand=True, padx=(0, 8))
        tk.Label(frame, text=title, bg=BG, fg='#7893ac', anchor='w', font=('Microsoft YaHei UI', 9)).pack(fill='x', pady=(0, 5))
        box = ttk.Combobox(frame, textvariable=variable, values=[self.tr(v) for v in values] if isinstance(variable,DisplayVar) else values, state='readonly' if readonly else 'normal', width=15)
        box.pack(fill='x', ipady=4)
        if isinstance(variable,DisplayVar): self.localized_widgets.append((box, list(values)))
        return box

    def update_reticle_preview(self,*args):
        theme={'Green · Routine':'green','Blue · Active':'blue','Yellow · Urgent':'yellow','Red · Critical':'red'}[self.color.get()]
        a,b,w=PALETTES[theme]
        tile=render_reticle(STYLES[self.reticle_style.get()],a,b,w,self.reticle_size.get()/100)
        background=Image.new('RGBA',(88,88),(17,30,45,255))
        tile=tile.resize((round(tile.width*.45),round(tile.height*.45)),Image.Resampling.LANCZOS)
        if self.cross.get():background.alpha_composite(tile,((88-tile.width)//2,(88-tile.height)//2))
        self.reticle_photo=ImageTk.PhotoImage(background)
        self.reticle_preview.configure(image=self.reticle_photo)
        self.reticle_size_label.configure(text=self.tr(f'Reticle size {round(self.reticle_size.get())}%'))

    def build_overlay(self):
        self.hud = tk.Toplevel(self.root)
        self.hud.withdraw()
        self.hud.title('AEGIS MK.IV / Optical Visor')
        self.hud.overrideredirect(True)
        self.hud.attributes('-topmost', True)
        self.width, self.height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.hud.geometry(f'{self.width}x{self.height}+0+0')
        self.hud.update_idletasks()
        hwnd = user32.GetAncestor(self.hud.winfo_id(), 2)
        self.surface = LayeredSurface(hwnd, self.width, self.height)
        self.renderer = VisorRenderer(self.width, self.height)

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.boot_started = time.monotonic()
            self.render_fault = False
            self.draw()
            self.hud.deiconify()
        else:
            self.hud.withdraw()

    def full_preview(self):
        self.noise.set('High'); self.cover.set('Deep'); self.motion.set(True)
        self.brightness.set(94)
        self.boot_started = time.monotonic()
        if not self.visible: self.toggle()
        self.status.set('Full tactical preview / Timer not started' if not self.active else 'Full tactical visor enabled')

    def light_preview(self):
        self.noise.set('Low'); self.cover.set('Light')
        self.brightness.set(75)
        if not self.visible: self.toggle()

    def reload_stories(self):
        self.stories = {}
        errors = []
        for path in sorted(self.story_folder().iterdir()):
            if path.suffix.lower() not in ('.json', '.md') or path.name.upper() == 'README.MD': continue
            try:
                story = load_story(path)
                self.stories[f'{story["title"]} · {path.stem}'] = (path.name, story)
            except (OSError, ValueError, TypeError) as e: errors.append(f'{path.name}: {e}')
        self.story_box['values'] = [self.tr('Free mission')] + list(self.stories)
        if self.story.get() not in self.stories: self.story.set('Free mission')
        self.select_story()
        if errors: self.dialog("showwarning", 'Some stories could not be imported', '\n'.join(errors))

    def select_story(self, event=None):
        if self.story.get() in self.stories:
            filename, story = self.stories[self.story.get()]
            titles = [f'{i+1:02d} / {m["title"]}' for i, m in enumerate(story['missions'])]
            self.chapter_box['values'] = titles
            progress = self.profile['progress'].get(filename, 0)
            index = min(max(0, progress if isinstance(progress, int) else 0), len(titles)-1)
            self.chapter_box.current(index)
        else:
            self.chapter_box['values'] = []; self.chapter.set(self.tr('Free mission'))
        self.show_briefing()

    def selected_mission(self):
        if self.story.get() not in self.stories: return None
        filename, story = self.stories[self.story.get()]
        index = self.chapter_box.current()
        if index < 0: return None
        return filename, index, story['missions'][index]

    def show_briefing(self, event=None):
        selected = self.selected_mission()
        text = 'Free mission ready. Enter a goal: reading, writing, coding, studying, or any screen-based work.\nYou can start without adding a storyline.'
        text=self.tr(text)
        if not self.stories:
            text += '\n\n'+self.tr('No stories for this language yet. Add JSON or Markdown files to:')+'\n'+str(self.story_folder())
        if selected:
            m = selected[2]; text = m['briefing'] + '\n\n'+self.tr('Objective: ') + m['objective']
        self.brief.configure(state='normal'); self.brief.delete('1.0', 'end')
        self.brief.insert('1.0', text); self.brief.configure(state='disabled')

    def refresh_audio(self):
        self.audio_box['values'] = [self.tr('Muted')] + [p.name for p in sorted((BASE / 'audio').glob('*.wav'))]

    def refresh_files(self):
        self.reload_stories(); self.refresh_audio()

    def play_audio(self):
        winsound.PlaySound(None, 0)
        if not self.active or self.timer.deadline is None or self.sound.get() == 'Muted': return
        path = BASE / 'audio' / self.sound.get()
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP | winsound.SND_NODEFAULT)
        except RuntimeError:
            self.status.set('Audio unavailable. Please use a PCM WAV file.')

    def start(self):
        if self.active: self.status.set('A mission is active. Extract or abort first.'); return
        try:
            minutes = int(self.minutes.get())
            if not 1 <= minutes <= 240: raise ValueError()
        except ValueError:
            self.dialog("showerror", 'Invalid duration', 'Enter a whole number of minutes from 1 to 240.'); return
        if not self.goal.get().strip():
            self.status.set('Enter a focus objective first.'); return
        self.active = {'goal': self.goal.get().strip(), 'difficulty': self.difficulty.get(),
                       'story': self.selected_mission(), 'break': False, 'started': time.strftime('%Y-%m-%d %H:%M:%S')}
        self.begin_timer(minutes)

    def begin_timer(self, minutes):
        self.timer = Timer(minutes * 60); self.timer.start(); self.awaiting = False
        self.status.set('Mission active / Stay focused' if not self.active['break'] else 'Recovery / Take a screen break')
        if not self.visible: self.toggle()
        self.play_audio(); self.persist()

    def start_break(self, minutes):
        if self.active: self.status.set('Extract or abort the current mission first.'); return
        self.active = {'goal': 'Rest and recovery', 'break': True}
        self.begin_timer(minutes)

    def pause(self):
        if not self.active or self.awaiting: return
        if self.timer.deadline is None:
            self.timer.start(); self.status.set('Mission resumed'); self.play_audio()
        else:
            self.timer.pause(); self.status.set('Mission paused / Timer stopped'); winsound.PlaySound(None, 0)

    def finish(self):
        if not self.active: return
        task, timer = self.active, self.timer
        if not task['break']:
            points = reward(timer.total - timer.left(), task['difficulty'])
            self.profile['points'] += points
            self.profile['history'].append({'goal': task['goal'], 'started': task['started'], 'points': points,
                                           'seconds': int(timer.total - timer.left()), 'difficulty': task['difficulty']})
            if task['story']:
                filename, index, _ = task['story']
                self.profile['progress'][filename] = max(self.profile['progress'].get(filename, 0), index+1)
            self.status.set(f'Extraction complete / +{points} XP / Time for a break')
        else: self.status.set('Recovery complete / Ready for the next mission')
        self.clear_task(); self.update_rank(); self.persist(); self.select_story()

    def abort(self):
        if not self.active: return
        self.clear_task(); self.persist(); self.status.set('Mission aborted / No penalty. Restart anytime.')

    def clear_task(self):
        self.active = None; self.timer = None; self.awaiting = False
        self.clock_text.set('READY'); winsound.PlaySound(None, 0)

    def update_rank(self):
        points = self.profile['points']
        nxt = next((threshold for threshold, _ in RANKS if threshold > points), None)
        self.rank_label.configure(text=self.tr(f'{rank(points)}    /    {points} XP' + (f'    /    Next rank in {nxt-points} XP' if nxt else '    /    Highest rank')))

    def persist(self):
        self.profile['settings'] = {'language':self.language, 'color': self.color.get(), 'noise': self.noise.get(), 'cover': self.cover.get(), 'cross': self.cross.get(), 'motion': self.motion.get(), 'brightness': self.brightness.get()}
        self.profile['settings'].update(reticle_style=self.reticle_style.get(),reticle_size=self.reticle_size.get(),reticle_motion=self.reticle_motion.get())
        self.profile['pending_session'] = ({'task':self.active,'total':self.timer.total,'remaining':self.timer.left()}
                                           if self.active and self.timer else None)
        try: save_json(DATA, self.profile)
        except OSError as e: self.dialog("showerror", 'Save failed', f'Check folder write permissions: {e}')

    def restore_session(self):
        saved = self.profile.get('pending_session')
        if not saved: return
        try:
            task, total, remaining = dict(saved['task']), float(saved['total']), float(saved['remaining'])
            if 'difficulty' in task: task['difficulty'] = translate(task['difficulty'])
            if (not isinstance(task,dict) or not isinstance(task.get('goal'),str)
                or not isinstance(task.get('break'),bool) or not 0 <= remaining <= total <= 14400):
                raise ValueError('Invalid session')
            if not task['break'] and (task.get('difficulty') not in ('Light','Standard','Challenge') or 'started' not in task):
                raise ValueError('Invalid mission')
            self.active = task
            self.timer = Timer(total); self.timer.remaining = remaining
            self.awaiting = remaining <= 0
            self.clock_text.set(self.timer.display())
            self.goal.set(task['goal'])
            self.minutes.set(str(round(total/60)))
            if not task['break']:self.difficulty.set(task['difficulty'])
            self.status.set('Mission restored / Select Pause / Resume' if remaining>0 else 'Previous mission expired / Select Extract')
            if not self.visible:self.toggle()
        except (ValueError, TypeError, KeyError):
            self.profile['pending_session'] = None
            self.active = self.timer = None
            self.status.set('Could not restore the mission. XP and history are unchanged.')

    def draw(self):
        started = time.perf_counter()
        theme = {'Green · Routine':'green','Blue · Active':'blue','Yellow · Urgent':'yellow','Red · Critical':'red'}[self.color.get()]
        config = HUDConfig(theme=theme, density={'Low':0,'Medium':1,'High':2}.get(self.noise.get(),2),
                           deep=self.cover.get()=='Deep', crosshair=self.cross.get(),
                           motion=self.motion.get(),reticle_style=STYLES[self.reticle_style.get()],
                           reticle_scale=self.reticle_size.get()/100,reticle_motion=self.reticle_motion.get())
        state = HUDState(chapter='Free mission', clock=self.clock_text.get(), goal=self.goal.get(), points=self.profile['points'],
                         rank=rank(self.profile['points']), local_time=time.strftime('%H:%M:%S'),
                         difficulty=self.difficulty.get(), boot=time.monotonic()-self.boot_started)
        if self.active:
            state.goal = self.active['goal']
            state.stage = 'RECOVERY' if self.active['break'] else 'MISSION ACTIVE'
            if self.timer.deadline is None: state.stage = 'PAUSED'
            if self.awaiting: state.stage = 'EXTRACTION READY'
            elif self.timer.deadline is not None and self.timer.left() <= 300 and not self.active['break']:
                state.stage = 'EXTRACTION WINDOW'
            state.progress = 1-self.timer.left()/self.timer.total
            seconds = int(self.timer.total-self.timer.left())
            state.elapsed = f'{seconds//60:02d}:{seconds%60:02d}'
            if not self.active['break']:
                state.difficulty = self.active['difficulty']
                if self.active['story']:
                    filename,index,mission=self.active['story']
                    state.chapter=mission['title']
                    for name,story in self.stories.values():
                        if name==filename and index<len(story['missions']):
                            state.chapter=story['missions'][index]['title'];break
        frame = self.renderer.render(config,state,time.monotonic())
        self.surface.present(frame, opacity=round(self.brightness.get()*2.55))
        self.last_render_ms = (time.perf_counter()-started)*1000

    def tick(self):
        while not self.hotkey_events.empty():
            ident = self.hotkey_events.get_nowait()
            if ident == 1: self.toggle()
            elif ident == 2: self.pause()
            elif ident == 3: self.close(); return
            elif ident == 0: self.hotkey_label.configure(text=self.tr('\n'.join(self.hotkey_descriptions)))
        if self.active:
            self.clock_text.set(self.timer.display())
            if self.timer.left() <= 0 and not self.awaiting:
                self.awaiting = True; self.timer.pause(); winsound.PlaySound(None, 0)
                self.status.set('Time is up / Select Extract to finish' if not self.active['break'] else 'Break complete / Select Extract')
        frame_start = time.perf_counter()
        if self.visible and not self.render_fault:
            try:
                self.draw()
            except Exception as e:
                self.render_fault = True
                self.visible = False
                self.hud.withdraw()
                self.status.set(f'Visor display failed: {e}')
        # Target 24 fps; preserve responsiveness if a large display is slower.
        interval = 42 if self.visible and self.motion.get() else 200
        spent = (time.perf_counter()-frame_start)*1000
        self.root.after(max(8, int(interval-spent)), self.tick)

    def listen_hotkeys(self):
        self.hotkey_descriptions = []
        for ident, key in [(1, 0x48), (2, 0x50), (3, 0x51)]:
            action = {1:'Toggle HUD', 2:'Pause / Resume', 3:'Quit'}[ident]
            registered = False
            for mods, prefix in [(0x4003, 'Ctrl + Alt'), (0x4007, 'Ctrl + Alt + Shift')]:
                if user32.RegisterHotKey(None, ident, mods, key):
                    self.hotkeys.append(ident)
                    self.hotkey_descriptions.append(f'{prefix} + {chr(key)}    {action}')
                    registered = True
                    break
            if not registered: self.hotkey_descriptions.append(f'{action}: Hotkey unavailable; use the button')
        self.hotkey_events.put(0)
        msg = wintypes.MSG()
        while not self.hotkey_stop.wait(0.03):
            while user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                self.hotkey_events.put(msg.wParam)
        for ident in self.hotkeys: user32.UnregisterHotKey(None, ident)

    def close(self):
        self.persist(); winsound.PlaySound(None, 0)
        self.hotkey_stop.set(); self.hotkey_thread.join(timeout=1)
        self.surface.close()
        self.root.destroy()

if __name__ == '__main__':
    try: user32.SetProcessDPIAware()
    except OSError: pass
    for folder in ['storylines', 'audio', 'data']: (BASE / folder).mkdir(exist_ok=True)
    application = App()
    import sys
    if '--preview' in sys.argv:
        application.root.after(300, application.full_preview)
    application.root.mainloop()
