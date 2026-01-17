#!/usr/bin/env python3
"""
Complete verified grading of all picks from the spreadsheet.
"""

# Verified scores from ESPN API
GAMES = {
    # date: {(away, home): (away_score, home_score, away_h1, home_h1)}
    '2025-12-10': {
        ('wisconsin', 'nebraska'): (60, 90, 31, 47),
        ('duquesne', 'boise'): (64, 86, 30, 45),
    },
    '2025-12-11': {
        ('iowa', 'iowa state'): (62, 66, 33, 25),
        ('n dakota st', 'bakersfield'): (80, 69, 40, 30),
        ('saint josephs', 'syracuse'): (63, 71, 32, 38),
    },
    '2025-12-12': {
        ('texas', 'uconn'): (63, 71, 34, 43),
        ('ca baptist', 'e washington'): (88, 83, 46, 36),
    },
    '2025-12-13': {
        ('memphis', 'louisville'): (73, 99, 37, 57),
        ('smu', 'lsu'): (77, 89, 44, 47),
        ('uc riverside', 'byu'): (53, 100, 32, 49),
        ('arizona', 'alabama'): (96, 75, 39, 41),
        ('ucla', 'gonzaga'): (72, 82, 40, 45),
        ('mississippi st', 'utah'): (82, 74, 32, 42),
        ('pepperdine', 'bakersfield'): (70, 62, 33, 26),
        ('tennessee st', 'unlv'): (63, 60, 29, 33),
        ('west virginia', 'ohio state'): (88, 89, 37, 27),
    },
    '2025-12-14': {
        ('charlotte', 'charleston'): (67, 74, 33, 39),
    },
    '2025-12-15': {
        ('niagara', 'vcu'): (58, 84, 24, 43),
    },
    '2025-12-16': {
        ('florida st', 'dayton'): (69, 97, 31, 42),
        ('marist', 'georgia tech'): (76, 87, 36, 44),
        ('butler', 'uconn'): (60, 79, 25, 39),
        ('towson', 'kansas'): (49, 73, 25, 36),
        ('pacific', 'byu'): (57, 93, 20, 41),
        ('montana st', 'cal poly'): (83, 80, 40, 41),
        ('oral roberts', 'missouri st'): (62, 63, 24, 30),
        ('abilene christian', 'arizona'): (62, 96, 30, 46),
        ('kansas city', 'oklahoma'): (67, 89, 29, 44),
        ('south carolina', 'clemson'): (61, 68, 30, 33),
        ('nc a&t', 'unc greensboro'): (71, 65, 36, 30),
        ('etsu', 'north carolina'): (58, 77, 24, 38),
    },
    '2025-12-17': {
        ('arizona st', 'ucla'): (77, 90, 33, 45),
        ('portland', 'oregon'): (69, 94, 41, 51),
    },
    '2025-12-18': {
        ('pepperdine', 'long beach st'): (78, 81, 37, 36),
    },
    '2025-12-21': {
        ('north dakota', 'nebraska'): (55, 78, 26, 24),
        ('norfolk st', 'utep'): (72, 71, 42, 32),
    },
    '2025-12-23': {
        ('villanova', 'seton hall'): (64, 56, 31, 27),
    },
}

def get_game(date, team1, team2):
    if date not in GAMES:
        return None
    t1, t2 = team1.lower(), team2.lower()
    for (away, home), scores in GAMES[date].items():
        if ((t1 in away or away in t1 or t1 in home or home in t1) and
            (t2 in away or away in t2 or t2 in home or home in t2)):
            away_score, home_score, away_h1, home_h1 = scores
            return {
                'away': away, 'home': home,
                'away_score': away_score, 'home_score': home_score,
                'away_h1': away_h1, 'home_h1': home_h1,
                'total': away_score + home_score,
                'h1_total': away_h1 + home_h1,
                'h2_total': (away_score - away_h1) + (home_score - home_h1),
                'spread': home_score - away_score,  # positive = home won
                'h1_spread': home_h1 - away_h1,
                'h2_spread': (home_score - home_h1) - (away_score - away_h1),
            }
    return None

# All picks from the image
PICKS = [
    # (date, away, home, segment, pick_type, pick_team, line)
    # pick_type: 'spread', 'total', 'ml', 'over', 'under'

    # Dec 10
    ('2025-12-10', 'Wisconsin', 'Nebraska', 'FG', 'spread', 'Wisconsin', 2),
    ('2025-12-10', 'Wisconsin', 'Nebraska', '1H', 'spread', 'Wisconsin', 1),
    ('2025-12-10', 'Wisconsin', 'Nebraska', 'FG', 'under', None, 158.5),
    ('2025-12-10', 'Duquesne', 'Boise', 'FG', 'under', None, 150.5),
    ('2025-12-10', 'Duquesne', 'Boise', '1H', 'spread', 'Duquesne', 8),
    ('2025-12-10', 'Duquesne', 'Boise', 'FG', 'spread', 'Duquesne', 14),

    # Dec 11
    ('2025-12-11', 'Iowa', 'Iowa State', '1H', 'over', None, 66.5),
    ('2025-12-11', 'Iowa', 'Iowa State', 'FG', 'over', None, 141),
    ('2025-12-11', 'Iowa', 'Iowa State', 'FG', 'spread', 'Iowa', 11.5),
    ('2025-12-11', 'N Dakota St', 'Bakersfield', '2H', 'spread', 'Bakersfield', 2),
    ('2025-12-11', 'N Dakota St', 'Bakersfield', '2H', 'under', None, 81.5),
    ('2025-12-11', 'N Dakota St', 'Bakersfield', 'FG', 'under', None, 149.5),
    ('2025-12-11', 'N Dakota St', 'Bakersfield', 'FG', 'spread', 'Bakersfield', 6.5),
    ('2025-12-11', 'Saint Josephs', 'Syracuse', '2H', 'under', None, 77),

    # Dec 12
    ('2025-12-12', 'Texas', 'UConn', 'FG', 'over', None, 146.5),
    ('2025-12-12', 'Texas', 'UConn', 'FG', 'spread', 'Texas', 12),
    ('2025-12-12', 'Texas', 'UConn', '1H', 'spread', 'Texas', 6.5),
    ('2025-12-12', 'Texas', 'UConn', '1H', 'over', None, 69.5),
    ('2025-12-12', 'CA Baptist', 'E Washington', 'FG', 'spread', 'CA Baptist', -3.5),
    ('2025-12-12', 'CA Baptist', 'E Washington', 'FG', 'over', None, 154.5),
    ('2025-12-12', 'CA Baptist', 'E Washington', '1H', 'spread', 'CA Baptist', -2),
    ('2025-12-12', 'CA Baptist', 'E Washington', '1H', 'over', None, 72.5),

    # Dec 13
    ('2025-12-13', 'Memphis', 'Louisville', 'FG', 'spread', 'Memphis', 17),
    ('2025-12-13', 'Memphis', 'Louisville', '1H', 'spread', 'Memphis', 10),
    ('2025-12-13', 'Memphis', 'Louisville', '1H', 'over', None, 77),
    ('2025-12-13', 'SMU', 'LSU', 'FG', 'over', None, 158.5),
    ('2025-12-13', 'SMU', 'LSU', '1H', 'over', None, 75),
    ('2025-12-13', 'SMU', 'LSU', '2H', 'under', None, 83),
    ('2025-12-13', 'UC Riverside', 'BYU', 'FG', 'spread', 'UC Riverside', 34),
    ('2025-12-13', 'UC Riverside', 'BYU', 'FG', 'over', None, 155),
    ('2025-12-13', 'Arizona', 'Alabama', 'FG', 'spread', 'Alabama', -3),
    ('2025-12-13', 'Arizona', 'Alabama', 'FG', 'ml', 'Alabama', None),
    ('2025-12-13', 'Arizona', 'Alabama', '1H', 'spread', 'Alabama', 1.5),
    ('2025-12-13', 'Arizona', 'Alabama', '2H', 'spread', 'Alabama', 3),
    ('2025-12-13', 'Arizona', 'Alabama', '2H', 'under', None, 92.5),
    ('2025-12-13', 'UCLA', 'Gonzaga', '2H', 'spread', 'Gonzaga', -5),
    ('2025-12-13', 'UCLA', 'Gonzaga', '2H', 'over', None, 79),
    ('2025-12-13', 'Mississippi St', 'Utah', 'FG', 'over', None, 153.5),
    ('2025-12-13', 'Mississippi St', 'Utah', '1H', 'over', None, 72),
    ('2025-12-13', 'Pepperdine', 'Bakersfield', 'FG', 'over', None, 148),
    ('2025-12-13', 'Pepperdine', 'Bakersfield', '1H', 'over', None, 69.5),
    ('2025-12-13', 'Tennessee St', 'UNLV', 'FG', 'over', None, 161),
    ('2025-12-13', 'Tennessee St', 'UNLV', '1H', 'over', None, 76),
    ('2025-12-13', 'West Virginia', 'Ohio State', 'FG', 'spread', 'Ohio State', -3.5),
    ('2025-12-13', 'West Virginia', 'Ohio State', 'FG', 'over', None, 145),
    ('2025-12-13', 'West Virginia', 'Ohio State', '1H', 'over', None, 68.5),

    # Dec 14
    ('2025-12-14', 'Charlotte', 'Charleston', 'FG', 'over', None, 140.5),
    ('2025-12-14', 'Charlotte', 'Charleston', '1H', 'over', None, 66),
    ('2025-12-14', 'Charlotte', 'Charleston', 'FG', 'spread', 'Charlotte', 6),
    ('2025-12-14', 'Charlotte', 'Charleston', '1H', 'spread', 'Charlotte', 3.5),

    # Dec 15
    ('2025-12-15', 'Niagara', 'VCU', 'FG', 'spread', 'Niagara', 31),
    ('2025-12-15', 'Niagara', 'VCU', '1H', 'spread', 'Niagara', 18),

    # Dec 16
    ('2025-12-16', 'Florida St', 'Dayton', 'FG', 'under', None, 161.5),
    ('2025-12-16', 'Marist', 'Georgia Tech', 'FG', 'under', None, 140.5),
    ('2025-12-16', 'South Carolina', 'Clemson', '1H', 'over', None, 67),
    ('2025-12-16', 'NC A&T', 'UNC Greensboro', 'FG', 'over', None, 147),
    ('2025-12-16', 'Kansas City', 'Oklahoma', 'FG', 'spread', 'Kansas City', 29),
    ('2025-12-16', 'Kansas City', 'Oklahoma', '1H', 'spread', 'Kansas City', 16.5),
    ('2025-12-16', 'Oral Roberts', 'Missouri St', '1H', 'over', None, 69),
    ('2025-12-16', 'ETSU', 'North Carolina', 'FG', 'under', None, 151),
    ('2025-12-16', 'Butler', 'UConn', 'FG', 'over', None, 145.5),
    ('2025-12-16', 'Butler', 'UConn', '1H', 'over', None, 70),
    ('2025-12-16', 'Butler', 'UConn', '2H', 'over', None, 75),
    ('2025-12-16', 'Towson', 'Kansas', 'FG', 'spread', 'Kansas', -16),
    ('2025-12-16', 'Pacific', 'BYU', 'FG', 'spread', 'Pacific', 23),
    ('2025-12-16', 'Abilene Christian', 'Arizona', 'FG', 'spread', 'Abilene Christian', 33.5),
    ('2025-12-16', 'Abilene Christian', 'Arizona', '1H', 'spread', 'Abilene Christian', 19.5),
    ('2025-12-16', 'Montana St', 'Cal Poly', 'FG', 'under', None, 159),

    # Dec 17
    ('2025-12-17', 'Arizona St', 'UCLA', 'FG', 'over', None, 143),
    ('2025-12-17', 'Arizona St', 'UCLA', '1H', 'over', None, 68),
    ('2025-12-17', 'Portland', 'Oregon', 'FG', 'spread', 'Portland', 19.5),
    ('2025-12-17', 'Portland', 'Oregon', '1H', 'spread', 'Portland', 11.5),

    # Dec 18
    ('2025-12-18', 'Pepperdine', 'Long Beach St', 'FG', 'spread', 'Pepperdine', -4),
    ('2025-12-18', 'Pepperdine', 'Long Beach St', 'FG', 'ml', 'Pepperdine', None),
    ('2025-12-18', 'Pepperdine', 'Long Beach St', 'FG', 'over', None, 141),

    # Dec 21
    ('2025-12-21', 'North Dakota', 'Nebraska', 'FG', 'spread', 'North Dakota', 29.5),
    ('2025-12-21', 'North Dakota', 'Nebraska', 'FG', 'over', None, 152.5),
    ('2025-12-21', 'North Dakota', 'Nebraska', '1H', 'spread', 'North Dakota', 17.5),
    ('2025-12-21', 'North Dakota', 'Nebraska', '1H', 'under', None, 73.5),
    ('2025-12-21', 'North Dakota', 'Nebraska', '2H', 'over', None, 77.5),
    ('2025-12-21', 'Norfolk St', 'UTEP', '1H', 'ml', 'Norfolk St', None),
    ('2025-12-21', 'Norfolk St', 'UTEP', '1H', 'under', None, 62.5),
    ('2025-12-21', 'Norfolk St', 'UTEP', 'FG', 'ml', 'Norfolk St', None),

    # Dec 23
    ('2025-12-23', 'Villanova', 'Seton Hall', 'FG', 'over', None, 136),
    ('2025-12-23', 'Villanova', 'Seton Hall', 'FG', 'spread', 'Seton Hall', -1),
    ('2025-12-23', 'Villanova', 'Seton Hall', 'FG', 'ml', 'Seton Hall', None),
    ('2025-12-23', 'Villanova', 'Seton Hall', '1H', 'over', None, 62.5),
    ('2025-12-23', 'Villanova', 'Seton Hall', '1H', 'spread', 'Seton Hall', 0),
]

def grade_pick(pick, game):
    date, away, home, segment, pick_type, pick_team, line = pick

    if segment == 'FG':
        total = game['total']
        spread = game['spread']
        away_score = game['away_score']
        home_score = game['home_score']
    elif segment == '1H':
        total = game['h1_total']
        spread = game['h1_spread']
        away_score = game['away_h1']
        home_score = game['home_h1']
    else:  # 2H
        total = game['h2_total']
        spread = game['h2_spread']
        away_score = game['away_score'] - game['away_h1']
        home_score = game['home_score'] - game['home_h1']

    if pick_type == 'over':
        if total > line:
            return 'WIN', f'Total {total} > {line}'
        if total < line:
            return 'LOSS', f'Total {total} < {line}'
        return 'PUSH', f'Total {total} = {line}'

    if pick_type == 'under':
        if total < line:
            return 'WIN', f'Total {total} < {line}'
        if total > line:
            return 'LOSS', f'Total {total} > {line}'
        return 'PUSH', f'Total {total} = {line}'

    if pick_type == 'ml':
        pick_lower = pick_team.lower()
        # Determine if pick team is home or away
        is_home = pick_lower in game['home']
        if is_home:
            if home_score > away_score:
                return 'WIN', f'{pick_team} won {home_score}-{away_score}'
            return 'LOSS', f'{pick_team} lost {home_score}-{away_score}'
        if away_score > home_score:
            return 'WIN', f'{pick_team} won {away_score}-{home_score}'
        return 'LOSS', f'{pick_team} lost {away_score}-{home_score}'

    if pick_type == 'spread':
        pick_lower = pick_team.lower()
        is_home = pick_lower in game['home'] or game['home'] in pick_lower

        if is_home:
            # Home team spread
            cover_margin = spread + line
            if cover_margin > 0:
                return 'WIN', f'{pick_team} covered by {cover_margin:.1f} ({away_score}-{home_score})'
            if cover_margin < 0:
                return 'LOSS', f'{pick_team} lost by {-cover_margin:.1f} ({away_score}-{home_score})'
            return 'PUSH', f'Push ({away_score}-{home_score})'
        # Away team spread
        cover_margin = -spread + line
        if cover_margin > 0:
            return 'WIN', f'{pick_team} covered by {cover_margin:.1f} ({away_score}-{home_score})'
        if cover_margin < 0:
            return 'LOSS', f'{pick_team} lost by {-cover_margin:.1f} ({away_score}-{home_score})'
        return 'PUSH', f'Push ({away_score}-{home_score})'

    return 'UNKNOWN', 'Could not grade'


def main():
    print('=' * 120)
    print(' COMPLETE VERIFIED PICK GRADING')
    print('=' * 120)
    print()

    wins = losses = pushes = not_found = 0

    for pick in PICKS:
        date, away, home, segment, pick_type, pick_team, line = pick
        game = get_game(date, away, home)

        if not game:
            pick_desc = f'{pick_type.upper()} {pick_team or ""} {line or ""}'.strip()
            print(f'[?] NOT FOUND  {date} {away} @ {home} | {segment} {pick_desc}')
            not_found += 1
            continue

        result, explanation = grade_pick(pick, game)

        if result == 'WIN':
            wins += 1
            symbol = '[W]'
        elif result == 'LOSS':
            losses += 1
            symbol = '[L]'
        elif result == 'PUSH':
            pushes += 1
            symbol = '[P]'
        else:
            not_found += 1
            symbol = '[?]'

        pick_desc = f'{pick_type.upper()} {pick_team or ""} {line or ""}'.strip()
        print(f'{symbol} {result:<8} {date} {away} @ {home} | {segment} {pick_desc}')
        print(f'            -> {explanation}')

    print()
    print('=' * 120)
    print(' FINAL SUMMARY')
    print('=' * 120)
    total_graded = wins + losses + pushes
    win_pct = (wins / total_graded * 100) if total_graded > 0 else 0
    print(f'  WINS:      {wins}')
    print(f'  LOSSES:    {losses}')
    print(f'  PUSHES:    {pushes}')
    print(f'  NOT FOUND: {not_found}')
    print('  ---------------------')
    print(f'  TOTAL GRADED: {total_graded}')
    print(f'  WIN RATE:     {win_pct:.1f}%')

    # ROI calculation (standard -110 juice)
    if total_graded > 0:
        profit = (wins * 1.0) - (losses * 1.1) + (pushes * 0)
        roi = profit / (total_graded * 1.1) * 100
        print(f'  EST. ROI:     {roi:+.1f}%')

        units = wins - (losses * 1.1)
        print(f'  UNITS:        {units:+.1f}u')


if __name__ == '__main__':
    main()
