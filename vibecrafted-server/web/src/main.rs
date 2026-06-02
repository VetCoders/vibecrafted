#![recursion_limit = "512"]

// Vibecrafted server console - Leptos 0.8 SSR bin.

#[cfg(feature = "ssr")]
#[tokio::main]
async fn main() {
    use axum::Router;
    use leptos::config::get_configuration;
    use leptos::logging::log;
    use leptos_axum::{LeptosRoutes, generate_route_list};
    use vibecrafted_server_web::app::{App, shell};

    let conf = get_configuration(None).expect("LeptosOptions config");
    let leptos_options = conf.leptos_options;
    let addr = leptos_options.site_addr;
    let routes = generate_route_list(App);

    let app: Router = Router::new()
        .leptos_routes(&leptos_options, routes, {
            let opts = leptos_options.clone();
            move || shell(opts.clone())
        })
        .fallback(leptos_axum::file_and_error_handler(shell))
        .with_state(leptos_options);

    log!("listening on http://{addr}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .expect("bind site_addr");
    axum::serve(listener, app.into_make_service())
        .await
        .expect("axum::serve");
}

#[cfg(not(feature = "ssr"))]
fn main() {
    // Hydrate path lives in lib.rs::hydrate(); this stub keeps plain cargo build valid.
}
