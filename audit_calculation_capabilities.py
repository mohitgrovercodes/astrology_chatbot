# audit_calculation_capabilities.py
"""
Comprehensive Audit: Calculation Capabilities vs. Actual Usage

This script checks:
1. What calculation engines/functions exist in your codebase
2. What's being called by the orchestrator
3. What's being passed to validation
4. What's missing from the data pipeline
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

class CalculationAudit:
    """Audit all calculation capabilities."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.capabilities = {
            'vedic': {},
            'western': {},
            'common': {}
        }
        self.usage = {
            'orchestrator': set(),
            'validation': set(),
            'api': set()
        }
        self.missing = []
        
    def scan_vedic_capabilities(self):
        """Scan all Vedic calculation capabilities."""
        print("\n" + "="*80)
        print("SCANNING VEDIC ENGINE CAPABILITIES")
        print("="*80)
        
        vedic_path = self.project_root / "src/engines/vedic"
        capabilities = {}
        
        # 1. Divisional Charts
        div_chart_file = vedic_path / "divisional_charts.py"
        if div_chart_file.exists():
            with open(div_chart_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find all D-chart functions
            d_charts = re.findall(r'def compute_(d\d+)_(\w+)', content)
            capabilities['divisional_charts'] = {
                f"{chart.upper()}": name.title() 
                for chart, name in d_charts
            }
            
        # 2. Dasha Systems
        dasha_file = vedic_path / "dasha_systems.py"
        if dasha_file.exists():
            with open(dasha_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find dasha calculation functions
            dashas = re.findall(r'def calculate_(\w+_dasha)', content)
            capabilities['dasha_systems'] = list(set(dashas))
            
        # 3. Aspects & Yogas
        aspects_file = vedic_path / "aspects_yogas.py"
        if aspects_file.exists():
            with open(aspects_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find yoga detection functions
            yogas = re.findall(r'def (find_\w+_yoga|detect_\w+)', content)
            capabilities['yogas'] = list(set(yogas))
            
        # 4. Graha Stats (Planetary Strengths)
        graha_file = vedic_path / "graha_stats.py"
        if graha_file.exists():
            with open(graha_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find strength calculation functions
            strengths = re.findall(r'def calculate_(\w+_bala)', content)
            capabilities['planetary_strengths'] = list(set(strengths))
            
        # 5. Rashi & Nakshatra
        rashi_file = vedic_path / "rashi_nakshatra.py"
        if rashi_file.exists():
            capabilities['rashi_nakshatra'] = ['nakshatra_calculation', 'pada_calculation', 'rashi_lord']
            
        self.capabilities['vedic'] = capabilities
        return capabilities
    
    def scan_western_capabilities(self):
        """Scan all Western calculation capabilities."""
        print("\n" + "="*80)
        print("SCANNING WESTERN ENGINE CAPABILITIES")
        print("="*80)
        
        western_path = self.project_root / "src/engines/western"
        capabilities = {}
        
        # 1. Aspects
        aspects_file = western_path / "western_aspects.py"
        if aspects_file.exists():
            capabilities['aspects'] = ['conjunction', 'opposition', 'trine', 'square', 'sextile', 'quincunx']
            
        # 2. Dignities
        dignities_file = western_path / "western_dignities.py"
        if dignities_file.exists():
            capabilities['dignities'] = ['essential_dignities', 'accidental_dignities', 'rulership', 'exaltation']
            
        # 3. Houses
        houses_file = western_path / "western_houses.py"
        if houses_file.exists():
            with open(houses_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            house_systems = re.findall(r'def calculate_(\w+)_houses', content)
            capabilities['house_systems'] = list(set(house_systems))
            
        self.capabilities['western'] = capabilities
        return capabilities
    
    def scan_orchestrator_usage(self):
        """Scan what orchestrator actually uses."""
        print("\n" + "="*80)
        print("SCANNING ORCHESTRATOR USAGE")
        print("="*80)
        
        orch_file = self.project_root / "src/orchestration/orchestrator.py"
        if not orch_file.exists():
            print("❌ Orchestrator not found")
            return set()
        
        with open(orch_file, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        usage = set()
        
        # Check what's being calculated
        if 'calculate_birth_chart' in content:
            usage.add('birth_chart')
        if 'calculate_dasha' in content or 'vimshottari' in content.lower():
            usage.add('vimshottari_dasha')
        if 'calculate_transits' in content:
            usage.add('transits')
        if 'divisional' in content.lower() or 'navamsa' in content.lower():
            usage.add('divisional_charts')
        if 'yoga' in content.lower():
            usage.add('yogas')
        if 'strength' in content.lower() or 'bala' in content.lower():
            usage.add('planetary_strengths')
            
        self.usage['orchestrator'] = usage
        return usage
    
    def scan_validation_requirements(self):
        """Scan what validation engine requires."""
        print("\n" + "="*80)
        print("SCANNING VALIDATION REQUIREMENTS")
        print("="*80)
        
        rules_file = self.project_root / "optimized/tiered_rules.json"
        if not rules_file.exists():
            print("❌ Validation rules not found")
            return set()
        
        import json
        with open(rules_file, encoding='utf-8', errors='ignore') as f:
            rules = json.load(f)
        
        requirements = set()
        
        # Scan all rules for data requirements
        all_rules = rules.get('tier_3', [])
        
        for rule in all_rules:
            conditions = rule.get('conditions', [])
            for cond in conditions:
                field = cond.get('field', '')
                
                # Categorize requirements
                if 'D9' in field or 'navamsa' in field.lower():
                    requirements.add('D9_navamsa')
                elif 'D10' in field or 'dasamsa' in field.lower():
                    requirements.add('D10_dasamsa')
                elif 'D7' in field:
                    requirements.add('D7_saptamsa')
                elif 'divisional_charts' in field:
                    requirements.add('divisional_charts')
                elif 'dasha' in field.lower():
                    requirements.add('dasha_periods')
                elif 'yoga' in field.lower():
                    requirements.add('yogas')
                elif 'strength' in field.lower() or 'bala' in field.lower():
                    requirements.add('planetary_strengths')
                elif 'transit' in field.lower():
                    requirements.add('transits')
        
        self.usage['validation'] = requirements
        return requirements
    
    def find_missing_capabilities(self):
        """Find gaps between capabilities and usage."""
        print("\n" + "="*80)
        print("ANALYZING GAPS")
        print("="*80)
        
        # Get what validation needs
        validation_needs = self.usage.get('validation', set())
        
        # Get what orchestrator provides
        orchestrator_provides = self.usage.get('orchestrator', set())
        
        # Find missing
        missing = validation_needs - orchestrator_provides
        
        self.missing = list(missing)
        return missing
    
    def generate_report(self):
        """Generate comprehensive audit report."""
        report = []
        
        report.append("\n" + "█"*80)
        report.append("  CALCULATION CAPABILITIES AUDIT REPORT")
        report.append("█"*80)
        
        # 1. Vedic Capabilities
        report.append("\n" + "="*80)
        report.append("1. VEDIC ENGINE CAPABILITIES (What You Have)")
        report.append("="*80)
        
        vedic = self.capabilities.get('vedic', {})
        
        if 'divisional_charts' in vedic:
            report.append(f"\n📊 Divisional Charts ({len(vedic['divisional_charts'])} available):")
            for chart, name in sorted(vedic['divisional_charts'].items()):
                report.append(f"  ✅ {chart:<6} - {name}")
        
        if 'dasha_systems' in vedic:
            report.append(f"\n⏰ Dasha Systems ({len(vedic['dasha_systems'])} available):")
            for dasha in vedic['dasha_systems']:
                report.append(f"  ✅ {dasha}")
        
        if 'yogas' in vedic:
            report.append(f"\n🎯 Yogas ({len(vedic['yogas'])} detection functions):")
            for yoga in vedic['yogas'][:10]:  # Show first 10
                report.append(f"  ✅ {yoga}")
            if len(vedic['yogas']) > 10:
                report.append(f"  ... and {len(vedic['yogas']) - 10} more")
        
        if 'planetary_strengths' in vedic:
            report.append(f"\n💪 Planetary Strengths ({len(vedic['planetary_strengths'])} calculations):")
            for strength in vedic['planetary_strengths']:
                report.append(f"  ✅ {strength}")
        
        # 2. Western Capabilities
        report.append("\n" + "="*80)
        report.append("2. WESTERN ENGINE CAPABILITIES (What You Have)")
        report.append("="*80)
        
        western = self.capabilities.get('western', {})
        
        if 'aspects' in western:
            report.append(f"\n🔗 Aspects ({len(western['aspects'])} types):")
            for aspect in western['aspects']:
                report.append(f"  ✅ {aspect}")
        
        if 'dignities' in western:
            report.append(f"\n👑 Dignities ({len(western['dignities'])} types):")
            for dignity in western['dignities']:
                report.append(f"  ✅ {dignity}")
        
        if 'house_systems' in western:
            report.append(f"\n🏠 House Systems ({len(western['house_systems'])} available):")
            for system in western['house_systems']:
                report.append(f"  ✅ {system}")
        
        # 3. Current Usage
        report.append("\n" + "="*80)
        report.append("3. WHAT'S CURRENTLY BEING USED")
        report.append("="*80)
        
        report.append("\n📊 Orchestrator Usage:")
        for item in sorted(self.usage.get('orchestrator', set())):
            report.append(f"  ✅ {item}")
        
        report.append("\n🔍 Validation Requirements:")
        for item in sorted(self.usage.get('validation', set())):
            report.append(f"  ⚠️  {item}")
        
        # 4. Missing/Gaps
        report.append("\n" + "="*80)
        report.append("4. GAPS - CAPABILITIES NOT BEING UTILIZED")
        report.append("="*80)
        
        if self.missing:
            report.append("\n❌ CRITICAL GAPS (Validation needs but orchestrator doesn't provide):")
            for item in sorted(self.missing):
                report.append(f"  ❌ {item}")
            
            report.append("\n🔧 RECOMMENDED ACTIONS:")
            for item in sorted(self.missing):
                if 'D9' in item or 'navamsa' in item:
                    report.append(f"  → Fix prepare_chart_for_validation() to include D9 data")
                elif 'D10' in item:
                    report.append(f"  → Include D10 (career) divisional chart in validation data")
                elif 'yoga' in item:
                    report.append(f"  → Add yoga detection to chart calculation flow")
                elif 'strength' in item:
                    report.append(f"  → Calculate and include planetary strength (Shadbala)")
        else:
            report.append("\n✅ No critical gaps found!")
        
        # 5. Available but Unused
        report.append("\n" + "="*80)
        report.append("5. AVAILABLE BUT UNUSED CAPABILITIES")
        report.append("="*80)
        
        vedic_charts = set(vedic.get('divisional_charts', {}).keys())
        used_charts = {'D1', 'D9', 'D10'}  # Commonly used
        unused_charts = vedic_charts - used_charts
        
        if unused_charts:
            report.append("\n📊 Unused Divisional Charts (available for future use):")
            for chart in sorted(unused_charts):
                name = vedic['divisional_charts'][chart]
                report.append(f"  ⚪ {chart:<6} - {name}")
        
        # Summary
        report.append("\n" + "="*80)
        report.append("SUMMARY")
        report.append("="*80)
        
        total_vedic = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in vedic.values())
        total_western = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in western.values())
        total_used = len(self.usage.get('orchestrator', set()))
        total_required = len(self.usage.get('validation', set()))
        total_missing = len(self.missing)
        
        report.append(f"\n📊 Total Capabilities Available: ~{total_vedic + total_western}")
        report.append(f"✅ Currently Used: {total_used}")
        report.append(f"⚠️  Required by Validation: {total_required}")
        report.append(f"❌ Missing/Not Integrated: {total_missing}")
        
        if total_missing == 0:
            report.append("\n🎉 ALL VALIDATION REQUIREMENTS ARE MET!")
        else:
            report.append(f"\n⚠️  {total_missing} gap(s) need to be addressed")
        
        report.append("\n" + "="*80 + "\n")
        
        return "\n".join(report)
    
    def run_full_audit(self):
        """Run complete audit."""
        self.scan_vedic_capabilities()
        self.scan_western_capabilities()
        self.scan_orchestrator_usage()
        self.scan_validation_requirements()
        self.find_missing_capabilities()
        
        report = self.generate_report()
        print(report)
        
        # Save to file
        output_file = self.project_root / "CALCULATION_AUDIT_REPORT.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📝 Report saved to: {output_file}")
        
        return {
            'capabilities': self.capabilities,
            'usage': self.usage,
            'missing': self.missing
        }


if __name__ == "__main__":
    print("Starting Comprehensive Calculation Audit...")
    print("This will scan all calculation engines and identify gaps.\n")
    
    auditor = CalculationAudit()
    results = auditor.run_full_audit()
    
    print("\n✅ Audit complete!")
    print("\nNext steps:")
    print("1. Review CALCULATION_AUDIT_REPORT.txt")
    print("2. Fix any critical gaps (especially D9 data pipeline)")
    print("3. Consider enabling unused capabilities for future features")