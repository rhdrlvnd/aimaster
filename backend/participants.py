"""Participant membership, including workspaces created with one successor."""

def successor_ids(state):
    handover = state['handover']
    if 'successor_ids' in handover:
        return handover['successor_ids']
    return [handover['successor_id']] if handover.get('successor_id') else []


def is_successor(state, user_id):
    return user_id in successor_ids(state)
