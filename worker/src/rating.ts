// Multiplayer Elo: every pair counts as one game won by the better place.
export function elo(ratingsByPlace: number[], k = 32): number[] {
  const n = ratingsByPlace.length;
  const deltas = ratingsByPlace.map(() => 0);
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const surprise = 1 - 1 / (1 + 10 ** ((ratingsByPlace[j] - ratingsByPlace[i]) / 400));
      deltas[i] += (k / (n - 1)) * surprise;
      deltas[j] -= (k / (n - 1)) * surprise;
    }
  }
  return deltas;
}
