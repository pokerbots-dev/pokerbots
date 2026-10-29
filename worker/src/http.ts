export class HttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export type Handler<C> = (ctx: C, params: string[]) => Promise<unknown>;
export type Routes<C> = Record<string, Handler<C>>;

export function route<C>(routes: Routes<C>, method: string, path: string): [Handler<C>, string[]] | undefined {
  const got = path.split("/");
  for (const [key, handler] of Object.entries(routes)) {
    const [m, pattern] = key.split(" ");
    const want = pattern.split("/");
    if (m !== method || want.length !== got.length) continue;
    const params: string[] = [];
    if (want.every((w, i) => (w.startsWith(":") ? params.push(decodeURIComponent(got[i])) : w === got[i]))) {
      return [handler, params];
    }
  }
}

export async function body<T>(req: Request): Promise<T> {
  try {
    return await req.json<T>();
  } catch {
    throw new HttpError(400, "invalid JSON");
  }
}

export function amount(value: unknown, minimum: number): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) {
    throw new HttpError(400, `minimum is ${minimum / 10_000}¢`);
  }
  return value as number;
}
