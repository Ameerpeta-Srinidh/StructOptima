import glob

files = glob.glob('pages/**/*.py', recursive=True)
for f in files:
    with open(f, encoding='utf-8') as file:
        content = file.read()
    
    new_content = content.replace('use_container_width=True', 'width="stretch"')
    
    if content != new_content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
