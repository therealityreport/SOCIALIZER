export function AppFooter() {
  return (
    <footer className="border-t border-border bg-background/80 px-6 py-3 text-xs text-muted-foreground">
      <p>
        © {new Date().getFullYear()} SOCIALIZER · Live Thread Sentiment Radar · Built for Bravo producers tracking fandom signal.
      </p>
    </footer>
  );
}
