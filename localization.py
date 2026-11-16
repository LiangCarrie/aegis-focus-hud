"""Display-only localization; model values stay English for save compatibility."""
import tkinter as tk
from english_ui import TRANSLATIONS
ZH = {v:k for k,v in TRANSLATIONS.items()}
ZH.update(dict(line.split('|',1) for line in '''Focus Mission Console|专注行动控制台
YOUR SCREEN. YOUR MISSION. / PERSONAL FOCUS SYSTEM|屏幕即任务现场 / 个人专注系统
01 / MISSION OBJECTIVE|01 / 任务目标
Focus minutes / Enter 1–240|专注分钟 / 可输入 1–240
Difficulty|任务难度
02 / STORY ARCHIVE|02 / 故事档案
Storyline|故事线
Chapter / Replay available|章节 / 可重玩
Open story folder|打开故事文件夹
Reload stories & audio|刷新故事与音频
03 / AEGIS MK.IV TACTICAL VISOR|03 / AEGIS MK.IV 战术面罩
Full tactical preview|全装战术预览
Stealth preview|轻装潜行
Alert palette|警戒配色
Visual noise|视觉噪声
Edge coverage|外围占据
Center reticle · Visual anchor|中央准星 · 保持视觉锚点
Reticle style|准星样式
Reticle size |准星大小 
Reticle motion · Ring/orbit edges only; center stays fixed|准星微动 · 仅圆环/轨道外圈，中心固定
Animated instruments · Turn off to freeze animations|动态光学仪表 · 关闭后冻结装饰动画
Visor brightness|面罩亮度
Local WAV soundscape / Loop playback|本地 WAV 音景 / 持续循环
04 / MISSION CONTROL|04 / 行动控制
Start mission|开始行动
Pause / Resume|暂停 / 继续
Extract|完成撤离
Abort|中止任务
Show / Hide HUD|显示 / 隐藏 HUD
5-min break|休息 5 分钟
15-min break|休息 15 分钟
Registering global hotkeys…|正在注册全局快捷键…
Clear center · Click-through · Primary display · Independent color & intensity|中央透明 · 鼠标穿透 · 主屏幕显示 · 配色与强度独立可调
Free mission|自由任务
Muted|静音
Complete your most important task|完成一件当前最重要的事
System ready / Awaiting mission|系统就绪 / 等待行动
Profile recovery|存档恢复
Full tactical preview / Timer not started|全装战术预览 / 未启动计时
Full tactical visor enabled|全装战术面罩已启用
Some stories could not be imported|部分故事未导入
Objective: |任务提示：
Audio unavailable. Please use a PCM WAV file.|音频无法播放，请使用 PCM WAV 文件
A mission is active. Extract or abort first.|已有任务，请先完成或中止
Invalid duration|时长无效
Enter a whole number of minutes from 1 to 240.|请输入 1–240 之间的整数分钟
Enter a focus objective first.|请先填写本次专注目标
Mission active / Stay focused|行动进行中 / 保持专注
Recovery / Take a screen break|恢复阶段 / 可以离开屏幕
Extract or abort the current mission first.|请先完成或中止当前任务
Rest and recovery|休息与恢复
Mission resumed|行动已继续
Mission paused / Timer stopped|行动暂停 / 时间已冻结
Extraction complete / +|撤离完成 / +
 XP / Time for a break| 积分 / 建议休息
Recovery complete / Ready for the next mission|恢复完成 / 可以开始下一次行动
Mission aborted / No penalty. Restart anytime.|任务已中止 / 不扣分，可随时重新开始
Next rank in |距晋升 
Highest rank|最高军衔
Save failed|存档失败
Check folder write permissions: |请检查目录写入权限：
Mission restored / Select Pause / Resume|已恢复上次行动 / 点击暂停或继续
Previous mission expired / Select Extract|上次行动已到期 / 等待撤离结算
Could not restore the mission. XP and history are unchanged.|上次任务快照无法恢复，积分和历史保持不变
Time is up / Select Extract to finish|时间到 / 点击完成撤离结算
Break complete / Select Extract|休息结束 / 点击完成撤离
Visor display failed: |面罩显示失败：
Toggle HUD|显隐 HUD
Quit|退出
: Hotkey unavailable; use the button|：快捷键被占用，请使用按钮
Invalid profile structure|存档结构不正确
Unreadable profile; backup saved as |存档无法读取，已保留为 
Free mission ready. Enter a goal: reading, writing, coding, studying, or any screen-based work.|自由任务已就绪。填写阅读、写作、编程或其他屏幕工作的目标。
You can start without adding a storyline.|未添加故事线也可以正常使用。
No stories for this language yet. Add JSON or Markdown files to:|此语言暂无故事。请将 JSON 或 Markdown 文件放入：'''.splitlines()))

def localize(text, language):
    if language != 'zh': return text
    if text in ZH: return ZH[text]
    # Longest-first, single pass prevents cascading partial translations.
    import re
    return re.sub('|'.join(re.escape(k) for k in sorted(ZH,key=len,reverse=True)),
                  lambda m: ZH[m.group()],text)

class DisplayVar(tk.StringVar):
    def __init__(self, owner, value='', fragments=False):
        self.owner=owner
        self.fragments=fragments
        self.canonical=value
        super().__init__(owner.root,value=self.display(value))
        owner.display_vars.append(self)
    def display(self,value):
        if self.fragments:return self.owner.tr(value)
        return ZH.get(value,value) if self.owner.language=="zh" else value
    def get(self):
        displayed=super().get()
        if displayed==self.display(self.canonical):return self.canonical
        self.canonical=next((k for k,v in ZH.items() if v==displayed),displayed)
        return self.canonical
    def set(self,value):
        self.canonical=value
        super().set(self.display(value))
    def refresh(self):
        super().set(self.display(self.canonical))
