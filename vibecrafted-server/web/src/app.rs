// Application shell + root component.

use leptos::prelude::*;
use leptos_meta::{Link, Meta, Title};
use leptos_router::components::{Route, Router, Routes};
use leptos_router::path;

use crate::theme::{Theme, ThemeBridge, provide_theme_context, use_theme};

#[cfg(feature = "ssr")]
pub fn shell(options: leptos::config::LeptosOptions) -> impl IntoView {
    use leptos_meta::MetaTags;

    const STYLE_TOKENS: &str = include_str!("../styles/tokens.css");
    const STYLE_FONTS: &str = include_str!("../styles/fonts.css");
    const STYLE_MAIN: &str = include_str!("../styles/main.css");

    view! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <AutoReload options=options.clone() />
                <HydrationScripts options/>
                <MetaTags/>
                <style>{STYLE_TOKENS}</style>
                <style>{STYLE_FONTS}</style>
                <style>{STYLE_MAIN}</style>
            </head>
            <body>
                <App/>
            </body>
        </html>
    }
}

#[component]
pub fn App() -> impl IntoView {
    leptos_meta::provide_meta_context();
    provide_theme_context();

    view! {
        <Router>
            <ThemeBridge />
            <Routes fallback=|| view! { <ConsolePage /> }>
                <Route path=path!("/") view=ConsolePage />
            </Routes>
        </Router>
    }
}

#[component]
pub fn ConsolePage() -> impl IntoView {
    let theme = use_theme();
    let theme_label = move || match theme.get() {
        Theme::Dark => "Light",
        Theme::Light => "Dark",
    };
    let theme_state = move || match theme.get() {
        Theme::Dark => "dark",
        Theme::Light => "light",
    };
    let toggle_theme = move |_| {
        theme.update(|current| {
            *current = current.toggle();
        });
    };

    view! {
        <Title text="vibecrafted server - console" />
        <Meta name="description" content="Vibecrafted server console shell." />
        <Meta name="theme-color" content="#0e0e0e" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/inter-var-latin.woff2" crossorigin="anonymous" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/jetbrains-mono-var-latin.woff2" crossorigin="anonymous" />

        <main class="server-console-shell">
            <section class="server-console-hero">
                <div class="server-console-topbar">
                    <span class="server-console-brand mono-cap">"vibecrafted server"</span>
                    <button
                        class="server-console-toggle"
                        type="button"
                        aria-label="Toggle color theme"
                        on:click=toggle_theme
                    >
                        {theme_label}
                    </button>
                </div>

                <div class="server-console-grid">
                    <div class="server-console-copy">
                        <p class="section-eyebrow">"local operator surface"</p>
                        <h1>"vibecrafted server — console"</h1>
                        <p>
                            "A quiet Leptos shell for the server control plane. "
                            "Wave 2 can wire live runs into this branded surface."
                        </p>
                    </div>

                    <aside class="server-console-panel" aria-label="Console status preview">
                        <div class="server-console-panel-head">
                            <span class="mono-cap">"shell"</span>
                            <span class="server-console-pill">{theme_state}</span>
                        </div>
                        <dl>
                            <div>
                                <dt>"runtime"</dt>
                                <dd>"cargo-leptos"</dd>
                            </div>
                            <div>
                                <dt>"render"</dt>
                                <dd>"SSR + hydrate"</dd>
                            </div>
                            <div>
                                <dt>"theme"</dt>
                                <dd>"data-theme"</dd>
                            </div>
                        </dl>
                    </aside>
                </div>
            </section>
        </main>
    }
}
