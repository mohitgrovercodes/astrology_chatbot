import os

REPLACEMENTS = {
    '->': '->',
    '[OK]': '[OK]',
    '[SAVE]': '[SAVE]',
    '[SEARCH]': '[SEARCH]',
    '[STATS]': '[STATS]',
    '*': '*',
    '*': '*',
    '[FAIL]': '[FAIL]',
    '[WARN]': '[WARN]',
    '[ASTRO]': '[ASTRO]',
    '[MOON]': '[MOON]',
    '[SUN]': '[SUN]',
    '[FIRE]': '[FIRE]',
    '[WATER]': '[WATER]',
    '[AIR]': '[AIR]',
    '[EARTH]': '[EARTH]',
    '[LAUNCH]': '[LAUNCH]',
    '[ALERT]': '[ALERT]',
    '[STOP]': '[STOP]',
    '[NOTE]': '[NOTE]',
    '[IDEA]': '[IDEA]'
}

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        modified = False
        for k, v in REPLACEMENTS.items():
            if k in content:
                content = content.replace(k, v)
                modified = True
                
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

if __name__ == '__main__':
    for root, dirs, files in os.walk('d:\\AI\\IMGProjects\\astro_chatbot\\astro_chatbot'):
        if 'venv' in root or '.git' in root or '.pycache' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                fix_file(os.path.join(root, file))
