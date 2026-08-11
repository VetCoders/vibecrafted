//! Shared operator chrome for every Leptos-owned vc-server route.
//!
//! The raw scaffold editor has its own document renderer, but mirrors this
//! route vocabulary so an operator never lands in a navigation dead end.

use leptos::prelude::*;

use crate::theme::{Theme, use_theme};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ServerSection {
    Overview,
    Runs,
    Lifecycle,
    Scaffold,
}

impl ServerSection {
    fn nav_class(self, section: Self) -> &'static str {
        if self == section {
            "server-nav-link is-active"
        } else {
            "server-nav-link"
        }
    }
}

#[component]
pub fn ServerFrame(active: ServerSection, status: String, children: Children) -> impl IntoView {
    let theme = use_theme();

    view! {
        <div class="server-app-shell">
            <header class="server-navbar">
                <div class="server-navbar-inner">
                    <a class="server-navbar-brand" href="/" aria-label="Vibecrafted server overview">
                        <span class="server-brand-mark" aria-hidden="true">"⌁"</span>
                        <span class="server-brand-copy">
                            <strong>"Vibecrafted server"</strong>
                            <small>{format!("control plane · {}", env!("VC_SERVER_VERSION"))}</small>
                        </span>
                    </a>
                    <div class="server-navbar-actions">
                        <span class="server-status-pill">
                            <span class="server-status-dot" aria-hidden="true"></span>
                            {status}
                        </span>
                        <a class="server-navbar-action" href="/scaffold">"Open scaffold"</a>
                        <button
                            type="button"
                            class="server-theme-toggle"
                            aria-label="Toggle color theme"
                            aria-pressed=move || theme.get() == Theme::Light
                            on:click=move |_| theme.update(|current| *current = current.toggle())
                        >
                            {move || theme.get().code()}
                        </button>
                    </div>
                </div>
            </header>

            <div class="server-app-body">
                <aside class="server-sidebar" aria-label="Vibecrafted server navigation">
                    <nav class="server-sidebar-nav">
                        <p class="server-nav-label">"Workspace"</p>
                        <a class=active.nav_class(ServerSection::Overview) href="/">
                            <span>"01"</span><strong>"Overview"</strong>
                        </a>
                        <a class=active.nav_class(ServerSection::Runs) href="/#fleet">
                            <span>"02"</span><strong>"Runs"</strong>
                        </a>
                        <a class=active.nav_class(ServerSection::Lifecycle) href="/#lifecycle">
                            <span>"03"</span><strong>"Lifecycle"</strong>
                        </a>
                        <a class=active.nav_class(ServerSection::Scaffold) href="/scaffold">
                            <span>"04"</span><strong>"Scaffold"</strong>
                        </a>
                    </nav>
                    <div class="server-sidebar-note">
                        <span class="server-status-dot" aria-hidden="true"></span>
                        <p>
                            <strong>"Runtime truth"</strong>
                            <small>"read-only control-plane projection"</small>
                        </p>
                    </div>
                </aside>

                <main class="server-route-main">{children()}</main>
            </div>

            <nav class="server-mobile-nav" aria-label="Vibecrafted server mobile navigation">
                <a class=active.nav_class(ServerSection::Overview) href="/">
                    <span>"01"</span><strong>"Overview"</strong>
                </a>
                <a class=active.nav_class(ServerSection::Runs) href="/#fleet">
                    <span>"02"</span><strong>"Runs"</strong>
                </a>
                <a class=active.nav_class(ServerSection::Lifecycle) href="/#lifecycle">
                    <span>"03"</span><strong>"Lifecycle"</strong>
                </a>
                <a class=active.nav_class(ServerSection::Scaffold) href="/scaffold">
                    <span>"04"</span><strong>"Scaffold"</strong>
                </a>
            </nav>
        </div>
    }
}
