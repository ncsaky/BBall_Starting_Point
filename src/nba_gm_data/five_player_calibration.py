"""Absolute, final-stage scouting decisions for the v11 new-career baseline."""
from dataclasses import replace

MARKER = 'five_player_scouting_v11'
SOURCE_ID = 'src_five_player_scouting_v11'


def apply_calibration(players, traits, payload):
    by_id = {p.id: p for p in players}
    targets = {}
    for row in payload['players']:
        player = by_id.get(row['player_id'])
        if player is None or player.name != row['name']:
            raise ValueError('Scouting calibration identity mismatch: ' + row['player_id'])
        for key, decision in row['traits'].items():
            targets[(player.id, key)] = (row, decision)
    output, seen = [], set()
    for trait in traits:
        pair = targets.get((trait.player_id, trait.trait_key))
        if pair is None:
            output.append(trait)
            continue
        row, decision = pair
        seen.add((trait.player_id, trait.trait_key))
        target = decision['target']
        if MARKER in trait.components:
            if trait.value != target:
                raise ValueError('Previously calibrated trait changed unexpectedly')
            output.append(trait)
            continue
        if abs(trait.value - decision['expected']) > .001:
            raise ValueError(f'Scouting baseline changed: {row["name"]} {trait.trait_key}: {trait.value}')
        output.append(replace(trait, value=target, confidence=min(trait.confidence, row['confidence']),
            source_ids=list(dict.fromkeys([*trait.source_ids, SOURCE_ID])),
            notes=trait.notes + ' V11 reviewed scouting calibration; not a measured box-stat refresh.',
            components={**trait.components, MARKER: {'previous': trait.value, 'target': target,
                'evidence': payload['evidence'], 'review_sha256': payload['review_sha256'],
                'decision_date': payload['decision_date'], 'version': payload['version']}}))
    if seen != targets.keys():
        raise ValueError('Missing scouting trait targets')
    return output
