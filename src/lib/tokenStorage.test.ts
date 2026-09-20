import { chunk, unchunk, CHUNK_SIZE } from './tokenStorage';

describe('chunk', () => {
  it('leaves a short value untouched', () => {
    expect(chunk('hola')).toEqual(['hola']);
  });

  it('splits a long value into chunks of the maximum size', () => {
    const value = 'x'.repeat(CHUNK_SIZE * 2 + 10);
    const parts = chunk(value);
    expect(parts).toHaveLength(3);
    expect(parts[0]).toHaveLength(CHUNK_SIZE);
    expect(parts[2]).toHaveLength(10);
  });

  it('unchunk reverses chunk without losing anything', () => {
    const value = JSON.stringify({ token: 'y'.repeat(5000) });
    expect(unchunk(chunk(value))).toBe(value);
  });
});
