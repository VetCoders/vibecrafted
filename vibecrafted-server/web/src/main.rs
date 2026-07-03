#![recursion_limit = "512"]

// Vibecrafted server console - Leptos 0.8 SSR bin.

#[cfg(feature = "ssr")]
#[tokio::main]
async fn main() {
    use std::net::SocketAddr;
    use std::path::PathBuf;

    use axum::Router;
    use axum::http::StatusCode;
    use axum::routing::get;
    use leptos::config::{Env, LeptosOptions};
    use leptos::logging::log;
    use leptos_axum::{LeptosRoutes, generate_route_list};
    use vibecrafted_server_web::app::{App, shell};
    use vibecrafted_server_web::control::api::control_routes;
    use vibecrafted_server_web::scaffold::api::scaffold_routes;

    fn configured_addr() -> SocketAddr {
        let cli_addr = std::env::args()
            .skip(1)
            .find_map(|arg| arg.strip_prefix("--addr=").map(ToOwned::to_owned))
            .or_else(|| {
                let mut args = std::env::args().skip(1);
                while let Some(arg) = args.next() {
                    if arg == "--addr" {
                        return args.next();
                    }
                }
                None
            });
        let configured = cli_addr
            .or_else(|| std::env::var("VC_SERVER_ADDR").ok())
            .or_else(|| std::env::var("LEPTOS_SITE_ADDR").ok())
            .unwrap_or_else(|| "127.0.0.1:3000".to_string());

        configured.parse().unwrap_or_else(|err| {
            eprintln!(
                "vc-server: invalid address `{configured}` ({err}); falling back to 127.0.0.1:3000"
            );
            "127.0.0.1:3000"
                .parse()
                .expect("default vc-server address parses")
        })
    }

    fn home_dir() -> Option<PathBuf> {
        std::env::var_os("HOME").map(PathBuf::from)
    }

    fn configured_site_root() -> String {
        if let Some(root) =
            std::env::var_os("VC_SERVER_SITE_ROOT").filter(|value| !value.is_empty())
        {
            return PathBuf::from(root).to_string_lossy().into_owned();
        }

        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(PathBuf::from));
        let mut candidates = Vec::new();

        if let Some(dir) = exe_dir {
            candidates.push(dir.join("vc-server-site"));
            candidates.push(dir.join("site"));
        }
        if let Some(home) = home_dir() {
            candidates.push(home.join(".local/share/vibecrafted/server/site"));
        }

        candidates
            .iter()
            .find(|path| path.exists())
            .cloned()
            .or_else(|| candidates.into_iter().next())
            .unwrap_or_else(|| PathBuf::from("target/site"))
            .to_string_lossy()
            .into_owned()
    }

    async fn favicon() -> StatusCode {
        StatusCode::NO_CONTENT
    }

    let leptos_options = LeptosOptions::builder()
        .output_name("vibecrafted-server-web")
        .site_root(configured_site_root())
        .site_pkg_dir("pkg")
        .env(Env::PROD)
        .site_addr(configured_addr())
        .reload_port(3025)
        .build();
    let addr = leptos_options.site_addr;
    let routes = generate_route_list(App);

    let app: Router = Router::new()
        .leptos_routes(&leptos_options, routes, {
            let opts = leptos_options.clone();
            move || shell(opts.clone())
        })
        .route("/favicon.ico", get(favicon))
        .merge(scaffold_routes())
        .merge(control_routes())
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
