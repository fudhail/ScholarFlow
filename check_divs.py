import re

with open("components/WorkspaceStudio.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# find return block
match = re.search(r'return \([\s\S]+?\);\n\};', content)
if match:
    block = match.group(0)
    lines = block.split("\n")
    depth = 0
    for i, line in enumerate(lines):
        opens = len(re.findall(r'<div\b', line))
        closes = len(re.findall(r'</div\s*>', line))
        if opens or closes:
            depth += (opens - closes)
            print(f"Line {i+354}: +{opens} -{closes} Depth: {depth} | {line.strip()}")
        
        o_frags = len(re.findall(r'<>', line))
        c_frags = len(re.findall(r'</>', line))
        if o_frags or c_frags:
            print(f"Line {i+354}: FRAG +{o_frags} -{c_frags} | {line.strip()}")
else:
    print("NO MATCH")
