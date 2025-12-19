"""
Generate switching-method atoms for CCNA Section 7.1.
"""

import json
import uuid
from sqlalchemy import create_engine, text

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings

# Switching method atoms to generate
ATOMS = [
    # MCQ atoms
    {
        'card_id': 'SWITCH-MCQ-001',
        'atom_type': 'mcq',
        'front': 'What are the two main categories of Ethernet switching methods?',
        'back': json.dumps({
            'options': ['Store-and-forward and cut-through', 'Fast-forward and fragment-free', 'Full-duplex and half-duplex', 'Static and dynamic'],
            'correct': 0,
            'explanation': 'The two main switching methods are store-and-forward (waits for entire frame) and cut-through (begins forwarding before full frame received). Fast-forward and fragment-free are subtypes of cut-through.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-MCQ-002',
        'atom_type': 'mcq',
        'front': 'Which switching method reads only the first 64 bytes of a frame before forwarding?',
        'back': json.dumps({
            'options': ['Fragment-free', 'Store-and-forward', 'Fast-forward', 'CRC-forward'],
            'correct': 0,
            'explanation': 'Fragment-free switching reads the first 64 bytes (collision window) to filter out runts caused by collisions before forwarding.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-MCQ-003',
        'atom_type': 'mcq',
        'front': 'Which switching method can forward frames with errors to the network?',
        'back': json.dumps({
            'options': ['Cut-through (fast-forward)', 'Store-and-forward', 'CRC-checked', 'Error-free switching'],
            'correct': 0,
            'explanation': 'Cut-through switching (especially fast-forward) starts forwarding before receiving the entire frame, so it cannot check the CRC and may forward corrupted frames.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-MCQ-004',
        'atom_type': 'mcq',
        'front': 'What does a store-and-forward switch check before forwarding a frame?',
        'back': json.dumps({
            'options': ['CRC in the FCS field', 'Only the destination MAC', 'The first 64 bytes', 'The IP header'],
            'correct': 0,
            'explanation': 'Store-and-forward switches receive the entire frame and calculate the CRC to compare with the Frame Check Sequence (FCS). Frames with errors are discarded.'
        }),
        'ccna_section_id': '7.1',
    },

    # True/False atoms
    {
        'card_id': 'SWITCH-TF-001',
        'atom_type': 'true_false',
        'front': 'Fast-forward switching has higher latency than store-and-forward switching.',
        'back': json.dumps({
            'answer': False,
            'explanation': 'Fast-forward has the LOWEST latency because it starts forwarding immediately after reading the destination MAC address, without waiting for the full frame.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-TF-002',
        'atom_type': 'true_false',
        'front': 'Fragment-free switching is a variation of cut-through switching.',
        'back': json.dumps({
            'answer': True,
            'explanation': 'Fragment-free is a type of cut-through switching. It reads the first 64 bytes to filter collision fragments, but still forwards before receiving the entire frame.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-TF-003',
        'atom_type': 'true_false',
        'front': 'Store-and-forward switching can detect and discard frames with CRC errors.',
        'back': json.dumps({
            'answer': True,
            'explanation': 'Store-and-forward receives the complete frame and checks the CRC against the FCS field. Frames with errors are dropped, preventing corruption from spreading.'
        }),
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-TF-004',
        'atom_type': 'true_false',
        'front': 'Cut-through switching is required for QoS analysis on a switch.',
        'back': json.dumps({
            'answer': False,
            'explanation': 'Store-and-forward is often required for QoS because it needs to read the entire frame to analyze Layer 3/4 headers for traffic prioritization.'
        }),
        'ccna_section_id': '7.1',
    },

    # Cloze atoms
    {
        'card_id': 'SWITCH-CLOZE-001',
        'atom_type': 'cloze',
        'front': '{{c1::Store-and-forward}} switching receives the entire frame and performs error checking using CRC before forwarding.',
        'back': 'Store-and-forward',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-CLOZE-002',
        'atom_type': 'cloze',
        'front': '{{c1::Fast-forward}} switching has the lowest latency because it begins forwarding after reading only the destination MAC address.',
        'back': 'Fast-forward',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-CLOZE-003',
        'atom_type': 'cloze',
        'front': '{{c1::Fragment-free}} switching reads the first {{c2::64}} bytes to filter out collision fragments before forwarding.',
        'back': 'Fragment-free; 64',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-CLOZE-004',
        'atom_type': 'cloze',
        'front': 'The {{c1::FCS (Frame Check Sequence)}} field contains the CRC value used by store-and-forward switches for error detection.',
        'back': 'FCS (Frame Check Sequence)',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-CLOZE-005',
        'atom_type': 'cloze',
        'front': 'Cut-through switching has two variations: {{c1::fast-forward}} and {{c2::fragment-free}}.',
        'back': 'fast-forward; fragment-free',
        'ccna_section_id': '7.1',
    },

    # Flashcard atoms
    {
        'card_id': 'SWITCH-FC-001',
        'atom_type': 'flashcard',
        'front': 'What is the main advantage of store-and-forward switching?',
        'back': 'Error detection - it performs CRC checking on the entire frame before forwarding, preventing corrupted frames from being sent to the network.',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-FC-002',
        'atom_type': 'flashcard',
        'front': 'What is the main advantage of cut-through switching?',
        'back': 'Lower latency - it begins forwarding the frame immediately after reading the destination MAC address, without waiting for the entire frame.',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-FC-003',
        'atom_type': 'flashcard',
        'front': 'Why does fragment-free switching read exactly 64 bytes?',
        'back': '64 bytes is the minimum valid Ethernet frame size. Frames smaller than this (runts) are typically caused by collisions. By reading 64 bytes, the switch can filter out these collision fragments.',
        'ccna_section_id': '7.1',
    },
    {
        'card_id': 'SWITCH-FC-004',
        'atom_type': 'flashcard',
        'front': 'When would you choose store-and-forward over cut-through switching?',
        'back': 'When error-free delivery is critical, when QoS features are needed (requires full frame analysis), or when connecting different speed ports (requires buffering).',
        'ccna_section_id': '7.1',
    },
]


def main():
    engine = create_engine(get_settings().database_url)
    created = 0
    skipped = 0

    with engine.connect() as conn:
        for atom in ATOMS:
            # Check if exists
            existing = conn.execute(
                text('SELECT id FROM learning_atoms WHERE card_id = :card_id'),
                {'card_id': atom['card_id']}
            ).fetchone()

            if existing:
                skipped += 1
                continue

            atom['id'] = str(uuid.uuid4())
            atom['source_file'] = 'CCNAModule4-7.txt'
            atom['quality_score'] = 0.85

            conn.execute(
                text('''
                    INSERT INTO learning_atoms
                    (id, card_id, front, back, atom_type, ccna_section_id, source_file, quality_score)
                    VALUES (:id, :card_id, :front, :back, :atom_type, :ccna_section_id, :source_file, :quality_score)
                '''),
                atom
            )
            created += 1

        conn.commit()
        print(f'Created {created} switching-method atoms, skipped {skipped} existing')


if __name__ == '__main__':
    main()
