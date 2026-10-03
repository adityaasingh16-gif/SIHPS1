import { Component } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

export { RouteErrorBoundary };

/**
 * Route-level error recovery: a crashed view never strands the user on a
 * blank page. Offers retry (remounts the route) and a calm way home, while
 * preserving every other part of the shell (sidebar, topbar, session).
 */
class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false, key: props.locationKey };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  static getDerivedStateFromProps(props, state) {
    // Navigating clears the failure so the next view mounts cleanly.
    if (props.locationKey !== state.key) {
      return { failed: false, key: props.locationKey };
    }
    return null;
  }

  componentDidCatch(error) {
    console.error("Route render failed:", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-risk-medium-subtle text-risk-medium">
          <AlertTriangle size={26} aria-hidden="true" />
        </div>
        <h2 className="text-lg font-bold text-fg">Something went wrong</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-fg-3">
          We couldn&apos;t show this view. Your session and the rest of the
          command center are unaffected.
        </p>
        <div className="mt-6 flex items-center justify-center gap-2.5">
          <button
            type="button"
            onClick={() => this.setState({ failed: false })}
            className="btn btn-primary"
          >
            <RefreshCw size={15} aria-hidden="true" />
            Try again
          </button>
          <Link to="/" className="btn btn-ghost">
            <Home size={15} aria-hidden="true" />
            Dashboard
          </Link>
        </div>
      </div>
    );
  }
}
