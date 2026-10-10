import { expect, test, type Page } from '@playwright/test';
import { es } from '../src/i18n/es';
import {
  createRoom,
  driveUntil,
  isShown,
  joinRoom,
  newDrive,
  openMobile,
  startGame,
  tokensOf,
  type Mobile,
} from './helpers';

const NAMES = ['Anfitriones', 'Azules', 'Verdes'] as const;

interface Objection {
  slot: number;
  before: number;
}

// Modo voz, 3 equipos. Un equipo gana una ficha al colocar bien (la carta se conoce al revelar),
// y en el turno de otro equipo el que tiene ficha objeta en un hueco distinto al del activo.
test('con una ficha se objeta en el turno de otro equipo y la ficha se gasta siempre', async ({ browser }) => {
  const mobiles: Mobile[] = [];
  for (let i = 0; i < 3; i++) mobiles.push(await openMobile(browser));
  const pages: Page[] = mobiles.map((m) => m.page);
  const [host, p2, p3] = pages as [Page, Page, Page];

  try {
    const code = await createRoom(host, { mode: 'voice', teams: 3, hostName: NAMES[0] });
    await joinRoom(p2, code, NAMES[1]);
    await joinRoom(p3, code, NAMES[2]);
    await startGame(host, 3);

    let tokenSeen = false;
    let objection: Objection | null = null;
    let objectionVerified = false;

    const totalTokens = async (): Promise<number[]> => Promise.all([0, 1, 2].map((s) => tokensOf(host, s)));

    // Cada móvil: si tiene el botón de objetar y tiene ficha, objeta en un hueco distinto al bloqueado;
    // si es otro equipo elegible, pasa.
    const objectOrPass = async (page: Page, i: number): Promise<boolean> => {
      const objectHere = page.getByRole('button', { name: es.game.objectHere });
      if (!(await isShown(objectHere))) return false;
      const before = await tokensOf(page, i);
      if (objection === null && before > 0) {
        // El turno es de otro equipo: el que objeta no tiene el turno.
        await expect(page.getByTestId('turn-banner')).not.toHaveText(es.game.yourTurn);
        const gap = page.getByTestId('gap-label');
        if ((await gap.textContent())?.includes(es.timeline.blocked)) {
          await page.getByRole('button', { name: es.timeline.next }).click();
        }
        await expect(gap).not.toContainText(es.timeline.blocked);
        await objectHere.click();
        objection = { slot: i, before };
      } else {
        await page.getByRole('button', { name: es.game.pass }).click();
      }
      return true;
    };

    // Fin del bucle: la revelación del turno con objeción muestra el resultado.
    const objectionRevealed = async (): Promise<boolean> => {
      const totals = await totalTokens();
      if (!tokenSeen && totals.some((t) => t > 0)) tokenSeen = true;
      if (objection === null) return false;
      const result = host.getByTestId('reveal-result');
      if (!(await isShown(result))) return false;
      const name = NAMES[objection.slot] ?? '';
      const text = (await result.textContent()) ?? '';
      objectionVerified = text.includes(es.game.objectionRight(name)) || text.includes(es.game.objectionWrong(name));
      return objectionVerified;
    };

    const finished = await driveUntil(pages, newDrive(), objectionRevealed, 200_000, objectOrPass);

    expect(tokenSeen, 'algún equipo debe ganar una ficha colocando bien y reclamando canción y artista').toBe(true);
    expect(objection, 'un equipo con ficha debe objetar en el turno de otro equipo').not.toBeNull();
    expect(finished, 'la revelación con la objeción debe llegar antes de que acabe la partida').toBe(true);

    const obj = objection as Objection | null;
    if (!obj) throw new Error('unreachable');
    const name = NAMES[obj.slot] ?? '';
    const reveal = host.getByTestId('reveal-result');

    // La revelación muestra el resultado de la objeción (bien o mal) y que el objetor gasta una ficha.
    await expect(reveal).toContainText(new RegExp(`${name} objetó (bien|mal)\\.`));
    await expect(reveal).toContainText(es.game.tokenLost(name));

    // D2: la ficha del objetor se gasta siempre (tokens antes de la objeción menos uno).
    await expect.poll(() => tokensOf(host, obj.slot), { timeout: 10_000 }).toBe(obj.before - 1);
  } finally {
    await Promise.all(mobiles.map((m) => m.ctx.close()));
  }
});
