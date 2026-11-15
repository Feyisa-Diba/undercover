import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";
import { useRoute, type Route } from "./route";

function Page({ route }: Readonly<{ route: Route }>) {
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "instructions":
      return <InstructionsPage />;
    case "queue":
      return <QueuePage />;
  }
}

export function App() {
  const route = useRoute();
  return (
    <div className="shell">
      <header className="masthead">
        <a className="brand" href="#/">
          UnderCover <span className="tagline">Claims desk</span>
        </a>
        <nav aria-label="Main">
          <a
            href="#/"
            aria-current={route.page === "queue" ? "page" : undefined}
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.page === "instructions" ? "page" : undefined}
          >
            Agent instructions
          </a>
        </nav>
      </header>
      <main>
        <Page route={route} />
      </main>
    </div>
  );
}
