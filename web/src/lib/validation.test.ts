import { describe, expect, it } from 'vitest';
import { toDateInput, validateCoordinates, validateHistoryRange } from './validation';

describe('validation', () => {
  it('validates coordinates', () => {
    expect(validateCoordinates(25.05, 121.57)).toBeNull();
    expect(validateCoordinates(91, 121.57)).toBe('Latitude must be between -90 and 90.');
    expect(validateCoordinates(25.05, 181)).toBe('Longitude must be between -180 and 180.');
  });

  it('rejects history start after history end', () => {
    expect(validateHistoryRange('2024-06-02', '2024-06-01', new Date('2024-06-10T00:00:00Z'))).toBe(
      'History start must be on or before History end.',
    );
  });

  it('rejects history end after today', () => {
    expect(validateHistoryRange('2024-06-01', '2024-06-11', new Date('2024-06-10T00:00:00Z'))).toBe(
      'History end cannot be after today.',
    );
  });

  it('accepts a valid history range', () => {
    expect(validateHistoryRange('2024-06-01', '2024-06-10', new Date('2024-06-10T00:00:00Z'))).toBeNull();
    expect(toDateInput(new Date('2024-06-10T00:00:00Z'))).toBe('2024-06-10');
  });
});
