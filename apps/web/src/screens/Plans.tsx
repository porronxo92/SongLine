import { Card, Screen } from '../components/ui';
import { es } from '../i18n/es';

export default function Plans() {
  const products = [
    [es.account.free, es.plans.prices[0], es.account.freeDetails],
    [es.account.premium, es.plans.prices[1], es.account.premiumDetails],
    [es.plans.packs, es.plans.prices[2], es.plans.packsCopy],
    [es.plans.playlists, es.plans.prices[3], es.plans.playlistsCopy],
  ];
  return (
    <Screen title={es.plans.plansTitle} back="/">
      <p className="help">{es.plans.soon}</p>
      {products.map(([name, price, description], index) => (
        <Card key={name} className="flex flex-col gap-3">
          <h2>{name}</h2>
          <p className="year text-3xl">{price}</p>
          {index > 0 ? <p className="overline">{es.plans.oneTime}</p> : null}
          <p>{description}</p>
        </Card>
      ))}
    </Screen>
  );
}
