#!/bin/bash
# Demo workflow showing analyzer -> agent pipeline

set -e

echo "🚀 PatchPro Demo Workflow"
echo "========================="
echo ""

# Step 1: Run analysis
echo "📊 Step 1: Running static analysis..."
patchpro analyze test_sample.py \
    --output artifact/findings.json \
    --format json \
    --artifacts-dir artifact/analysis

echo ""
echo "✅ Analysis complete! Findings saved to artifact/findings.json"
echo ""

# Step 2: Generate fixes with agent
echo "🤖 Step 2: Generating AI-powered fixes..."
patchpro agent artifact/findings.json \
    --output artifact/patchpro_report.md \
    --base-path . \
    --model gpt-4o-mini

echo ""
echo "✅ Fixes generated! Report saved to artifact/patchpro_report.md"
echo ""

# Step 3: Display report
echo "📄 Step 3: Displaying report..."
echo "=============================="
cat artifact/patchpro_report.md

echo ""
echo "🎉 Demo complete!"
echo ""
echo "Next steps:"
echo "  1. Review the generated report in artifact/patchpro_report.md"
echo "  2. Apply fixes manually or use the diffs"
echo "  3. Run tests to verify changes"
