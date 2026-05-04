export const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

export const validateCoordinates = (latitude: number, longitude: number): string | null => {
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    return 'Latitude must be between -90 and 90.';
  }
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    return 'Longitude must be between -180 and 180.';
  }
  return null;
};

export const validateHistoryRange = (
  historyStart: string,
  historyEnd: string,
  today: Date = new Date(),
): string | null => {
  if (historyStart > historyEnd) {
    return 'History start must be on or before History end.';
  }
  if (historyEnd > toDateInput(today)) {
    return 'History end cannot be after today.';
  }
  return null;
};
