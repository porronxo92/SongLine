import { Disc3, Music2, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, Screen } from '../components/ui';
import { es } from '../i18n/es';

export default function Landing() {
  return (
    <Screen
      actions={
        <Link className="btn btn-ghost" to="/cuenta">
          {es.account.title}
        </Link>
      }
    >
      <section className="flex flex-col items-center gap-5 py-8 text-center">
        <img src="/logo/songline-mark.svg" alt="" width={96} height={96} />
        <img src="/logo/songline-wordmark.svg" alt={es.appName} width={240} height={45} />
        <p className="overline">{es.landing.beta}</p>
        <h1 className="screen-title">{es.landing.tagline}</h1>
        <p className="max-w-md text-fg-2">{es.landing.description}</p>
        <Link className="btn btn-primary btn-xl w-full" to="/crear">
          {es.landing.start}
        </Link>
        <Link className="btn btn-secondary btn-xl w-full" to="/unirse">
          <Users aria-hidden />
          {es.landing.join}
        </Link>
        <Link className="btn btn-ghost" to="/jugar">
          {es.account.play}
        </Link>
      </section>
      <Card>
        <h2 className="mb-4">{es.landing.how}</h2>
        <ol className="flex list-decimal flex-col gap-4 pl-5">
          {es.landing.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </Card>
      <Card>
        <Disc3 className="mb-3 text-accent" aria-hidden />
        <h2>{es.landing.freeTitle}</h2>
        <p className="mt-2 text-fg-2">{es.landing.freeCopy}</p>
      </Card>
      <Card>
        <Music2 className="mb-3 text-accent" aria-hidden />
        <h2>{es.landing.premiumTitle}</h2>
        <p className="my-3 text-fg-2">{es.landing.premiumCopy}</p>
        <Link className="btn btn-secondary" to="/planes">
          {es.account.plans}
        </Link>
      </Card>
      <p className="help pb-6">{es.landing.audio}</p>
    </Screen>
  );
}

export function Plans() {
  const products = [
    [es.account.free, es.landing.prices[0], es.account.freeDetails],
    [es.account.premium, es.landing.prices[1], es.account.premiumDetails],
    [es.landing.packs, es.landing.prices[2], es.landing.packsCopy],
    [es.landing.playlists, es.landing.prices[3], es.landing.playlistsCopy],
  ];
  return (
    <Screen title={es.landing.plansTitle} back="/jugar">
      <p className="help">{es.landing.soon}</p>
      {products.map(([name, price, description], index) => (
        <Card key={name} className="flex flex-col gap-3">
          <h2>{name}</h2>
          <p className="year text-3xl">{price}</p>
          {index > 0 ? <p className="overline">{es.landing.oneTime}</p> : null}
          <p>{description}</p>
          {index === 0 ? (
            <Link className="btn btn-primary" to="/crear">
              {es.landing.start}
            </Link>
          ) : null}
        </Card>
      ))}
    </Screen>
  );
}
