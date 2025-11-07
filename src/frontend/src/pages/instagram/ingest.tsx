import { InstagramIngestForm } from '../../components/instagram/InstagramIngestForm';

export default function InstagramIngestPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-foreground">Instagram ingest</h1>
        <p className="text-muted-foreground">
          Pull Instagram posts via Apify, inspect per-username skip counts, and push qualifying posts into SOCIALIZER&apos;s datastore.
        </p>
      </div>
      <InstagramIngestForm />
    </div>
  );
}
