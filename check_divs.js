const fs = require('fs');
const content = fs.readFileSync('components/WorkspaceStudio.tsx', 'utf8');

const returnRegex = /return \([\s\S]+?\);\n\};/m;
const match = content.match(returnRegex);

if (match) {
    const block = match[0];
    const openDivs = (block.match(/<div\b/g) || []).length;
    const closeDivs = (block.match(/<\/div\s*>/g) || []).length;
    console.log(`Open: ${openDivs}, Close: ${closeDivs}`);
    
    // Let's print out every div log to see where they fail to match
    let depth = 0;
    const lines = block.split('\n');
    lines.forEach((line, i) => {
        const opens = (line.match(/<div\b/g) || []).length;
        const closes = (line.match(/<\/div\s*>/g) || []).length;
        if (opens > 0 || closes > 0) {
            depth += (opens - closes);
            console.log(`${i+1}: OP:${opens} CL:${closes} -> Depth:${depth} | ${line.trim()}`);
        }
    });

} else {
    console.log("No return block found!");
}
