import { describe, expect, it } from 'vitest';
import { nextDate } from './date';

describe('nextDate', () => {
  it('adds one day within the same month', () => {
    expect(nextDate('2024-06-01')).toBe('2024-06-02');
  });

  it('handles month rollover', () => {
    expect(nextDate('2024-01-31')).toBe('2024-02-01');
  });

  it('handles year rollover', () => {
    expect(nextDate('2024-12-31')).toBe('2025-01-01');
  });
});
