#!/usr/bin/env python3
"""
Comprehensive audit of team_aliases.json for canonicalization integrity.

Checks for:
1. Duplicate canonical names
2. Orphan alias targets (aliases pointing to non-existent canonicals)
3. Conflicting aliases (same alias mapping to different canonicals)
4. Similar canonical names that could cause confusion
5. Potential false-positive matches
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ALIASES_FILE = Path(__file__).parent.parent / "production_parity" / "team_aliases.json"


def normalize_for_comparison(name: str) -> str:
    """Normalize name for similarity comparison."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)  # Remove punctuation
    name = re.sub(r"\s+", " ", name).strip()
    return name


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def main():
    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    aliases = data.get("aliases", {})
    canonical_names = data.get("canonical_names", [])
    
    print("=" * 70)
    print("TEAM ALIASES CANONICALIZATION INTEGRITY AUDIT")
    print("=" * 70)
    print(f"File: {ALIASES_FILE}")
    print(f"Version: {data.get('version', 'unknown')}")
    print(f"Aliases: {len(aliases):,}")
    print(f"Canonical Names: {len(canonical_names):,}")
    
    issues = []
    
    # 1. Check for duplicate canonical names in the list
    print("\n" + "=" * 70)
    print("1. DUPLICATE CANONICAL NAMES CHECK")
    print("=" * 70)
    canonical_counts = Counter(canonical_names)
    duplicates = {k: v for k, v in canonical_counts.items() if v > 1}
    if duplicates:
        print("   ❌ DUPLICATES FOUND:")
        for name, count in duplicates.items():
            print(f"      {name}: appears {count} times")
            issues.append(f"Duplicate canonical: {name}")
    else:
        print("   ✅ No duplicates in canonical_names list")
    
    # 2. Check if all alias targets exist in canonical_names
    print("\n" + "=" * 70)
    print("2. ALIAS TARGET VALIDATION")
    print("=" * 70)
    alias_targets = set(aliases.values())
    canonical_set = set(canonical_names)
    orphan_targets = alias_targets - canonical_set
    if orphan_targets:
        print("   ⚠️  Alias targets NOT in canonical_names:")
        for t in sorted(orphan_targets):
            print(f"      {t}")
            issues.append(f"Orphan target: {t}")
    else:
        print("   ✅ All alias targets are valid canonical names")
    
    # 3. Check for conflicting aliases
    print("\n" + "=" * 70)
    print("3. CONFLICTING ALIASES CHECK")
    print("=" * 70)
    normalized_aliases = defaultdict(list)
    for alias, canonical in aliases.items():
        norm = alias.lower().strip()
        normalized_aliases[norm].append((alias, canonical))
    
    conflicts = {k: v for k, v in normalized_aliases.items() if len(set(c for _, c in v)) > 1}
    if conflicts:
        print("   ❌ CONFLICTING ALIASES (same alias maps to different canonicals):")
        for norm, mappings in conflicts.items():
            print(f"      \"{norm}\":")
            for alias, canonical in mappings:
                print(f"         -> {canonical}")
                issues.append(f"Conflict: {norm} -> multiple")
    else:
        print("   ✅ No conflicting aliases")
    
    # 4. Check for similar canonical names
    print("\n" + "=" * 70)
    print("4. SIMILAR CANONICAL NAMES (ensuring distinct)")
    print("=" * 70)
    
    # Known similar groups - these SHOULD be distinct
    similar_groups = [
        ["Alabama", "Alabama A&M", "Alabama St."],
        ["Tennessee", "Tennessee St.", "Tennessee Tech"],
        ["Georgia", "Georgia St.", "Georgia Tech", "Georgia Southern"],
        ["Texas", "Texas A&M", "Texas St.", "Texas Tech", "Texas Southern"],
        ["Kentucky", "Eastern Kentucky", "Western Kentucky"],
        ["Michigan", "Michigan St."],
        ["North Carolina", "North Carolina A&T"],
        ["Mississippi", "Mississippi St.", "Mississippi Valley St."],
        ["Illinois", "Illinois St."],
        ["Indiana", "Indiana St."],
        ["Ohio", "Ohio St."],
        ["Penn", "Penn St."],
        ["Arkansas", "Arkansas St.", "Arkansas Pine Bluff"],
        ["Louisiana", "Louisiana Tech", "Louisiana Monroe"],
        ["Missouri", "Missouri St."],
        ["New Mexico", "New Mexico St."],
    ]
    
    for group in similar_groups:
        in_canonical = [g for g in group if g in canonical_set]
        missing = [g for g in group if g not in canonical_set]
        status = "✅" if len(in_canonical) == len(group) else "⚠️"
        print(f"   {status} {group[0]:20} group: {in_canonical}")
        if missing:
            print(f"      Missing: {missing}")
    
    # 5. Check for dangerous alias patterns
    print("\n" + "=" * 70)
    print("5. DANGEROUS ALIAS PATTERNS CHECK")
    print("=" * 70)
    
    # Check aliases that are substrings of other team names
    dangerous_patterns = []
    for alias, canonical in aliases.items():
        alias_norm = normalize_for_comparison(alias)
        # Check if this alias could match a different canonical
        for other_canonical in canonical_names:
            if other_canonical == canonical:
                continue
            other_norm = normalize_for_comparison(other_canonical)
            # If alias is a prefix of another canonical name
            if other_norm.startswith(alias_norm) and len(alias_norm) < len(other_norm):
                if alias_norm in ["alabama", "tennessee", "georgia", "texas", "kentucky", 
                                   "michigan", "illinois", "indiana", "ohio", "penn",
                                   "arkansas", "louisiana", "missouri", "mississippi"]:
                    dangerous_patterns.append((alias, canonical, other_canonical))
    
    if dangerous_patterns:
        print("   ⚠️  Aliases that are prefixes of other canonicals:")
        shown = set()
        for alias, canonical, other in dangerous_patterns[:20]:
            key = (alias, canonical, other)
            if key not in shown:
                print(f"      '{alias}' -> '{canonical}' (could confuse with '{other}')")
                shown.add(key)
        print("\n   NOTE: This is expected - the resolver uses EXACT matching only!")
        print("   The ProductionTeamResolver will NOT fuzzy match these.")
    else:
        print("   ✅ No dangerous alias patterns found")
    
    # 6. Verify exact matching behavior
    print("\n" + "=" * 70)
    print("6. EXACT MATCHING VERIFICATION")
    print("=" * 70)
    
    # Test that similar names don't accidentally match
    test_cases = [
        ("Alabama", "Alabama"),
        ("Alabama A&M", "Alabama A&M"),
        ("Alabama State", "Alabama St."),  # Via alias
        ("alabama", "Alabama"),  # Case insensitive
        ("ALABAMA", "Alabama"),
        ("alabama a&m", "Alabama A&M"),
        ("alabama st", "Alabama St."),
        ("Tennessee", "Tennessee"),
        ("Tennessee State", "Tennessee St."),
        ("Tennessee Tech", "Tennessee Tech"),
        ("Illinois", "Illinois"),
        ("Illinois Chicago", "UIC"),  # Fixed mapping
        ("UIC", "UIC"),
    ]
    
    # Import resolver
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from production_parity.team_resolver import ProductionTeamResolver
    
    resolver = ProductionTeamResolver()
    
    all_passed = True
    for input_name, expected in test_cases:
        result = resolver.resolve(input_name)
        status = "✅" if result.canonical_name == expected else "❌"
        if result.canonical_name != expected:
            all_passed = False
            issues.append(f"Mismatch: {input_name} -> {result.canonical_name} (expected {expected})")
        print(f"   {status} '{input_name}' -> '{result.canonical_name}' (expected: '{expected}')")
    
    if all_passed:
        print("\n   ✅ All exact matching tests passed")
    
    # 7. Check that NO fuzzy matching occurs
    print("\n" + "=" * 70)
    print("7. FUZZY MATCHING PREVENTION CHECK")
    print("=" * 70)
    
    # These should NOT match anything (typos, partial names)
    should_not_match = [
        "Alabam",  # Missing letter
        "Tennesee",  # Typo
        "Georgai",  # Typo
        "Texs",  # Typo
        "Michign",  # Typo
        "Random University",  # Doesn't exist
        "Made Up State",  # Doesn't exist
    ]
    
    all_rejected = True
    for name in should_not_match:
        result = resolver.resolve(name)
        if result.canonical_name is not None:
            print(f"   ❌ '{name}' incorrectly matched to '{result.canonical_name}'")
            all_rejected = False
            issues.append(f"False positive: {name} -> {result.canonical_name}")
        else:
            print(f"   ✅ '{name}' correctly rejected (no match)")
    
    if all_rejected:
        print("\n   ✅ All invalid names correctly rejected (no fuzzy matching)")
    
    # Summary
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    
    if issues:
        print(f"   ❌ ISSUES FOUND: {len(issues)}")
        for issue in issues:
            print(f"      - {issue}")
    else:
        print("   ✅ ALL CHECKS PASSED - No issues found")
        print("\n   The team_aliases.json is the verified SINGLE SOURCE OF TRUTH")
        print("   for NCAAM team name canonicalization.")
    
    return 0 if not issues else 1


if __name__ == "__main__":
    exit(main())
