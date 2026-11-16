"""English labels and migration of legacy display settings."""
TRANSLATIONS = {'绿 · 常规': 'Green · Routine',
 '蓝 · 行动': 'Blue · Active',
 '黄 · 紧急': 'Yellow · Urgent',
 '红 · 危机': 'Red · Critical',
 '精密十字': 'Precision Cross',
 '光子圆点': 'Photon Dot',
 '全息圆环': 'Holographic Ring',
 '战术 T 型': 'Tactical T',
 '棱镜菱形': 'Prism Diamond',
 '鹰眼尖括': 'Eagle Chevron',
 '目标锁框': 'Target Brackets',
 '轨道核心': 'Orbital Core',
 '轻度': 'Light',
 '标准': 'Standard',
 '挑战': 'Challenge',
 '深度': 'Deep',
 '低': 'Low',
 '中': 'Medium',
 '高': 'High',
 '黄阶 · 见习': 'Yellow · Recruit',
 '黄阶 · 行动员': 'Yellow · Operative',
 '黄阶 · 精锐': 'Yellow · Elite',
 '玄阶 · 特勤': 'Mystic · Special Agent',
 '玄阶 · 指挥官': 'Mystic · Commander',
 '地阶 · 先锋': 'Earth · Vanguard',
 '地阶 · 守望者': 'Earth · Sentinel',
 '天阶 · 执行官': 'Heaven · Executor',
 '天阶 · 星域统领': 'Heaven · Star Marshal'}

def translate(value):
    return TRANSLATIONS.get(value, value)

def migrate_settings(settings):
    result = dict(settings)
    for key in ("color", "noise", "cover", "reticle_style"):
        if key in result: result[key] = translate(result[key])
    return result
