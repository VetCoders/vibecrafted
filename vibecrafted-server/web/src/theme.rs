// Theme mode - ported from loctree-com for data-theme + localStorage sync.

use leptos::prelude::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Theme {
    #[default]
    Dark,
    Light,
}

impl Theme {
    pub fn code(&self) -> &'static str {
        match self {
            Theme::Dark => "dark",
            Theme::Light => "light",
        }
    }

    pub fn from_code(code: &str) -> Option<Self> {
        match code {
            "dark" => Some(Theme::Dark),
            "light" => Some(Theme::Light),
            _ => None,
        }
    }

    pub fn toggle(self) -> Self {
        match self {
            Theme::Dark => Theme::Light,
            Theme::Light => Theme::Dark,
        }
    }
}

#[derive(Copy, Clone)]
pub struct ThemeContext {
    pub theme: RwSignal<Theme>,
}

impl ThemeContext {
    pub fn new() -> Self {
        Self {
            theme: RwSignal::new(Theme::default()),
        }
    }
}

impl Default for ThemeContext {
    fn default() -> Self {
        Self::new()
    }
}

pub fn provide_theme_context() {
    provide_context(ThemeContext::new());
}

pub fn use_theme() -> RwSignal<Theme> {
    expect_context::<ThemeContext>().theme
}

#[component]
pub fn ThemeBridge() -> impl IntoView {
    let theme = use_theme();

    Effect::new(move |_| {
        #[cfg(feature = "hydrate")]
        {
            if let Some(window) = web_sys::window()
                && let Ok(Some(storage)) = window.local_storage()
                && let Ok(Some(stored)) = storage.get_item("loct-theme")
                && let Some(restored) = Theme::from_code(&stored)
            {
                theme.set(restored);
            }
        }
    });

    Effect::new(move |_| {
        let current = theme.get();
        #[cfg(feature = "hydrate")]
        {
            if let Some(window) = web_sys::window() {
                if let Ok(Some(storage)) = window.local_storage() {
                    let _ = storage.set_item("loct-theme", current.code());
                }
                if let Some(document) = window.document()
                    && let Some(root) = document.document_element()
                {
                    let _ = root.set_attribute("data-theme", current.code());
                }
            }
        }
        #[cfg(not(feature = "hydrate"))]
        {
            let _ = current;
        }
    });

    view! { <></> }
}
