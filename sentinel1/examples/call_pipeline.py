"""Apel simplu, fara interfata web."""
import json
import os
from pathlib import Path
import ee
from sentinel1 import process_sentinel1


def main():
    # Proiectul apartine contului tau Earth Engine.
    project = os.environ.get('EE_PROJECT', 'floodlens-b7eb1')
    ee.Initialize(project=project)
    # Poti inlocui fisierul cu evenimentul primit de la backend.
    event = json.loads(Path(__file__).with_name('valencia.json').read_text())
    result = process_sentinel1(event, 'outputs/sentinel1_research')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
