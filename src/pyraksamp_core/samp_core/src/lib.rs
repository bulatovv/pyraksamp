use std::sync::Arc;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyraksamp_core::client::SampClient;
use pyraksamp_core::socks5;

// ── PySAMPClient ──────────────────────────────────────────────────────────────

// Stores original Python callables for getters.
struct PyCbs {
    on_connect:             Option<Py<PyAny>>,
    on_disconnect:          Option<Py<PyAny>>,
    on_rpc:                 Option<Py<PyAny>>,
    on_player_join:         Option<Py<PyAny>>,
    on_player_quit:         Option<Py<PyAny>>,
    on_chat:                Option<Py<PyAny>>,
    on_client_message:      Option<Py<PyAny>>,
    on_dialog:              Option<Py<PyAny>>,
    on_game_text:           Option<Py<PyAny>>,
    on_set_health:          Option<Py<PyAny>>,
    on_set_armour:          Option<Py<PyAny>>,
    on_set_position:        Option<Py<PyAny>>,
    on_checkpoint:          Option<Py<PyAny>>,
    on_checkpoint_disabled: Option<Py<PyAny>>,
    on_player_streamed_in:  Option<Py<PyAny>>,
    on_player_streamed_out: Option<Py<PyAny>>,
    on_player_name:         Option<Py<PyAny>>,
    on_toggle_controllable: Option<Py<PyAny>>,
    on_player_time:         Option<Py<PyAny>>,
    on_death_message:       Option<Py<PyAny>>,
    on_set_armed_weapon:    Option<Py<PyAny>>,
    on_spawn_info:          Option<Py<PyAny>>,
    on_player_team:         Option<Py<PyAny>>,
    on_put_in_vehicle:      Option<Py<PyAny>>,
    on_remove_from_vehicle: Option<Py<PyAny>>,
    on_player_color:        Option<Py<PyAny>>,
    on_world_time:          Option<Py<PyAny>>,
    on_toggle_spectating:   Option<Py<PyAny>>,
    on_wanted_level:        Option<Py<PyAny>>,
    on_weapon_ammo:         Option<Py<PyAny>>,
    on_gravity:             Option<Py<PyAny>>,
    on_weather:             Option<Py<PyAny>>,
    on_player_skin:         Option<Py<PyAny>>,
    on_set_interior:        Option<Py<PyAny>>,
    on_vehicle_streamed_in: Option<Py<PyAny>>,
    on_vehicle_streamed_out:Option<Py<PyAny>>,
    on_player_death:        Option<Py<PyAny>>,
    on_textdraw_show:          Option<Py<PyAny>>,
    on_textdraw_hide:          Option<Py<PyAny>>,
    on_textdraw_edit:          Option<Py<PyAny>>,
    on_textdraw_toggle_select: Option<Py<PyAny>>,
}

impl PyCbs {
    fn new() -> Self {
        PyCbs {
            on_connect: None, on_disconnect: None, on_rpc: None,
            on_player_join: None, on_player_quit: None,
            on_chat: None, on_client_message: None, on_dialog: None,
            on_game_text: None, on_set_health: None, on_set_armour: None,
            on_set_position: None, on_checkpoint: None, on_checkpoint_disabled: None,
            on_player_streamed_in: None, on_player_streamed_out: None,
            on_player_name: None, on_toggle_controllable: None,
            on_player_time: None, on_death_message: None, on_set_armed_weapon: None,
            on_spawn_info: None, on_player_team: None, on_put_in_vehicle: None,
            on_remove_from_vehicle: None, on_player_color: None, on_world_time: None,
            on_toggle_spectating: None, on_wanted_level: None, on_weapon_ammo: None,
            on_gravity: None, on_weather: None, on_player_skin: None,
            on_set_interior: None, on_vehicle_streamed_in: None,
            on_vehicle_streamed_out: None, on_player_death: None,
            on_textdraw_show: None, on_textdraw_hide: None,
            on_textdraw_edit: None, on_textdraw_toggle_select: None,
        }
    }
}

/// Acquire the GIL and run `f` only if the Python interpreter is still alive.
/// During interpreter shutdown (e.g. after Ctrl+C), `Py_IsInitialized` returns
/// 0 and calling `PyGILState_Ensure` / `PyGILState_Release` is unsafe, which
/// causes the "Fatal Python error: PyGILState_Release" crash.
#[inline]
fn with_gil_safe<F: FnOnce(Python<'_>)>(f: F) {
    if unsafe { pyo3::ffi::Py_IsInitialized() } != 0 {
        Python::with_gil(f);
    }
}

// Wrap a Python callable into an Arc<dyn Fn()> that acquires the GIL when called.
macro_rules! wrap0 {
    ($py_obj:expr) => {{
        let cb: Py<PyAny> = $py_obj;
        Arc::new(move || {
            with_gil_safe(|py| { let _ = cb.call0(py); });
        }) as Arc<dyn Fn() + Send + Sync>
    }};
}

macro_rules! wrap {
    ($py_obj:expr, $($arg:ident : $ty:ty),+) => {{
        let cb: Py<PyAny> = $py_obj;
        Arc::new(move |$($arg: $ty),+| {
            with_gil_safe(|py| {
                let _ = cb.call1(py, ($($arg,)+));
            });
        }) as Arc<dyn Fn($($ty),+) + Send + Sync>
    }};
}

#[pyclass(name = "SAMPClient")]
struct PySAMPClient {
    inner:  Arc<SampClient>,
    py_cbs: PyCbs,
}

// Helper: clone Py<PyAny> with GIL for getter return.
fn cloned(py: Python<'_>, opt: &Option<Py<PyAny>>) -> Option<Py<PyAny>> {
    opt.as_ref().map(|c| c.clone_ref(py))
}

#[pymethods]
impl PySAMPClient {
    #[new]
    #[pyo3(signature = (host, port, nickname, password="", gpci="", proxy_host=None, proxy_port=None, proxy_username=None, proxy_password=None))]
    fn new(
        host: &str,
        port: u16,
        nickname: &str,
        password: &str,
        gpci: &str,
        proxy_host: Option<&str>,
        proxy_port: Option<u16>,
        proxy_username: Option<&str>,
        proxy_password: Option<&str>,
    ) -> Self {
        let proxy = proxy_host.map(|h| socks5::ProxyConfig {
            host: h.to_string(),
            port: proxy_port.unwrap_or(1080),
            auth: proxy_username.map(|u| {
                (u.to_string(), proxy_password.unwrap_or("").to_string())
            }),
        });
        PySAMPClient {
            inner:  SampClient::new(host, port, nickname, password, gpci, proxy),
            py_cbs: PyCbs::new(),
        }
    }

    #[pyo3(signature = (timeout=15.0))]
    fn start(&self, py: Python, timeout: f64) -> bool {
        let inner = Arc::clone(&self.inner);
        let connected = py.allow_threads(move || inner.connect(timeout));
        if !connected { return false; }
        let inner = Arc::clone(&self.inner);
        std::thread::Builder::new()
            .name(format!("samp-recv-{}", self.inner.player_id()))
            .spawn(move || inner.run())
            .is_ok()
    }

    fn stop(&self)       { self.inner.stop(); }
    fn disconnect(&self) { self.inner.disconnect(); }

    #[pyo3(signature = (rpc_id, data=None, reliability=8))]
    fn send_rpc(&self, rpc_id: u8, data: Option<Vec<u8>>, reliability: u8) {
        self.inner.send_rpc(rpc_id, &data.unwrap_or_default(), reliability);
    }

    #[getter] fn is_connected(&self) -> bool { self.inner.is_connected() }
    #[getter] fn player_id(&self)    -> i32  { self.inner.player_id() }

    // ── Send helpers ──────────────────────────────────────────────────────────

    #[pyo3(signature = (dialog_id, button, list_item=0, text=None))]
    fn send_dialog_response(&self, dialog_id: u16, button: u8, list_item: u16, text: Option<&[u8]>) {
        self.inner.send_dialog_response(dialog_id, button, list_item, text.unwrap_or(b""));
    }

    #[pyo3(signature = (weapon_id=0, killer_id=0xFFFF))]
    fn send_death(&self, weapon_id: u8, killer_id: u16) {
        self.inner.send_death(weapon_id, killer_id);
    }

    #[pyo3(signature = (vehicle_id, is_passenger=false))]
    fn send_enter_vehicle(&self, vehicle_id: u16, is_passenger: bool) {
        self.inner.send_enter_vehicle(vehicle_id, is_passenger);
    }

    fn send_exit_vehicle(&self, vehicle_id: u16) { self.inner.send_exit_vehicle(vehicle_id); }
    fn send_command(&self, text: &[u8])          { self.inner.send_command(text); }

    // ── Callbacks ─────────────────────────────────────────────────────────────

    #[getter] fn get_on_connect(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_connect) }
    #[setter] fn set_on_connect(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_connect = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_connect = cb.map(|c| wrap0!(c));
    }

    #[getter] fn get_on_disconnect(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_disconnect) }
    #[setter] fn set_on_disconnect(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_disconnect = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_disconnect = cb.map(|c| wrap0!(c));
    }

    #[getter] fn get_on_rpc(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_rpc) }
    #[setter] fn set_on_rpc(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_rpc = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_rpc = cb.map(|c| {
            Arc::new(move |rpc_id: u8, data: Vec<u8>| {
                with_gil_safe(|py| {
                    let b = pyo3::types::PyBytes::new(py, &data);
                    let _ = c.call1(py, (rpc_id, b));
                });
            }) as Arc<dyn Fn(u8, Vec<u8>) + Send + Sync>
        });
    }

    #[getter] fn get_on_player_join(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_join) }
    #[setter] fn set_on_player_join(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_join = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_join = cb.map(|c| wrap!(c, pid: u16, name: String));
    }

    #[getter] fn get_on_player_quit(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_quit) }
    #[setter] fn set_on_player_quit(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_quit = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_quit = cb.map(|c| wrap!(c, pid: u16, reason: u8));
    }

    #[getter] fn get_on_chat(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_chat) }
    #[setter] fn set_on_chat(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_chat = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_chat = cb.map(|c| {
            Arc::new(move |pid: u16, text: Vec<u8>| {
                with_gil_safe(|py| { let _ = c.call1(py, (pid, PyBytes::new(py, &text))); });
            }) as Arc<dyn Fn(u16, Vec<u8>) + Send + Sync>
        });
    }

    #[getter] fn get_on_client_message(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_client_message) }
    #[setter] fn set_on_client_message(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_client_message = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_client_message = cb.map(|c| {
            Arc::new(move |color: u32, text: Vec<u8>| {
                with_gil_safe(|py| { let _ = c.call1(py, (color, PyBytes::new(py, &text))); });
            }) as Arc<dyn Fn(u32, Vec<u8>) + Send + Sync>
        });
    }

    #[getter] fn get_on_dialog(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_dialog) }
    #[setter] fn set_on_dialog(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_dialog = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_dialog = cb.map(|c| {
            Arc::new(move |did: u16, style: u8, title: Vec<u8>, btn1: Vec<u8>, btn2: Vec<u8>, body: Vec<u8>| {
                with_gil_safe(|py| {
                    let _ = c.call1(py, (did, style,
                        PyBytes::new(py, &title), PyBytes::new(py, &btn1),
                        PyBytes::new(py, &btn2),  PyBytes::new(py, &body)));
                });
            }) as Arc<dyn Fn(u16, u8, Vec<u8>, Vec<u8>, Vec<u8>, Vec<u8>) + Send + Sync>
        });
    }

    #[getter] fn get_on_game_text(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_game_text) }
    #[setter] fn set_on_game_text(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_game_text = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_game_text = cb.map(|c| wrap!(c, s: i32, ms: i32, text: String));
    }

    #[getter] fn get_on_set_health(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_set_health) }
    #[setter] fn set_on_set_health(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_set_health = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_set_health = cb.map(|c| wrap!(c, hp: f32));
    }

    #[getter] fn get_on_set_armour(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_set_armour) }
    #[setter] fn set_on_set_armour(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_set_armour = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_set_armour = cb.map(|c| wrap!(c, arm: f32));
    }

    #[getter] fn get_on_set_position(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_set_position) }
    #[setter] fn set_on_set_position(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_set_position = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_set_position = cb.map(|c| wrap!(c, x: f32, y: f32, z: f32));
    }

    #[getter] fn get_on_checkpoint(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_checkpoint) }
    #[setter] fn set_on_checkpoint(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_checkpoint = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_checkpoint = cb.map(|c| wrap!(c, x: f32, y: f32, z: f32, sz: f32));
    }

    #[getter] fn get_on_checkpoint_disabled(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_checkpoint_disabled) }
    #[setter] fn set_on_checkpoint_disabled(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_checkpoint_disabled = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_checkpoint_disabled = cb.map(|c| wrap0!(c));
    }

    #[getter] fn get_on_player_streamed_in(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_streamed_in) }
    #[setter] fn set_on_player_streamed_in(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_streamed_in = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_streamed_in = cb.map(|c| {
            Arc::new(move |pid: u16, team: u8, skin: i32, x: f32, y: f32, z: f32, rot: f32, color: u32, fs: u8| {
                with_gil_safe(|py| { let _ = c.call1(py, (pid, team, skin, x, y, z, rot, color, fs)); });
            }) as Arc<dyn Fn(u16, u8, i32, f32, f32, f32, f32, u32, u8) + Send + Sync>
        });
    }

    #[getter] fn get_on_player_streamed_out(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_streamed_out) }
    #[setter] fn set_on_player_streamed_out(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_streamed_out = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_streamed_out = cb.map(|c| wrap!(c, pid: u16));
    }

    #[getter] fn get_on_player_name(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_name) }
    #[setter] fn set_on_player_name(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_name = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_name = cb.map(|c| wrap!(c, pid: u16, name: String, success: u8));
    }

    #[getter] fn get_on_toggle_controllable(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_toggle_controllable) }
    #[setter] fn set_on_toggle_controllable(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_toggle_controllable = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_toggle_controllable = cb.map(|c| wrap!(c, v: u8));
    }

    #[getter] fn get_on_player_time(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_time) }
    #[setter] fn set_on_player_time(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_time = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_time = cb.map(|c| wrap!(c, hour: u8, minute: u8));
    }

    #[getter] fn get_on_death_message(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_death_message) }
    #[setter] fn set_on_death_message(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_death_message = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_death_message = cb.map(|c| wrap!(c, killer: u16, player: u16, weapon: u8));
    }

    #[getter] fn get_on_set_armed_weapon(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_set_armed_weapon) }
    #[setter] fn set_on_set_armed_weapon(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_set_armed_weapon = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_set_armed_weapon = cb.map(|c| wrap!(c, wid: u32));
    }

    #[getter] fn get_on_spawn_info(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_spawn_info) }
    #[setter] fn set_on_spawn_info(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_spawn_info = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_spawn_info = cb.map(|c| {
            Arc::new(move |team: u8, skin: u32, x: f32, y: f32, z: f32, rot: f32,
                           w1: u32, w2: u32, w3: u32, a1: u32, a2: u32, a3: u32| {
                with_gil_safe(|py| { let _ = c.call1(py, (team, skin, x, y, z, rot, w1, w2, w3, a1, a2, a3)); });
            }) as Arc<dyn Fn(u8, u32, f32, f32, f32, f32, u32, u32, u32, u32, u32, u32) + Send + Sync>
        });
    }

    #[getter] fn get_on_player_team(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_team) }
    #[setter] fn set_on_player_team(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_team = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_team = cb.map(|c| wrap!(c, pid: u16, team: u8));
    }

    #[getter] fn get_on_put_in_vehicle(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_put_in_vehicle) }
    #[setter] fn set_on_put_in_vehicle(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_put_in_vehicle = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_put_in_vehicle = cb.map(|c| wrap!(c, vid: u16, seat: u8));
    }

    #[getter] fn get_on_remove_from_vehicle(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_remove_from_vehicle) }
    #[setter] fn set_on_remove_from_vehicle(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_remove_from_vehicle = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_remove_from_vehicle = cb.map(|c| wrap0!(c));
    }

    #[getter] fn get_on_player_color(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_color) }
    #[setter] fn set_on_player_color(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_color = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_color = cb.map(|c| wrap!(c, pid: u16, color: u32));
    }

    #[getter] fn get_on_world_time(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_world_time) }
    #[setter] fn set_on_world_time(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_world_time = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_world_time = cb.map(|c| wrap!(c, hour: u8));
    }

    #[getter] fn get_on_toggle_spectating(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_toggle_spectating) }
    #[setter] fn set_on_toggle_spectating(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_toggle_spectating = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_toggle_spectating = cb.map(|c| wrap!(c, v: bool));
    }

    #[getter] fn get_on_wanted_level(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_wanted_level) }
    #[setter] fn set_on_wanted_level(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_wanted_level = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_wanted_level = cb.map(|c| wrap!(c, level: u8));
    }

    #[getter] fn get_on_weapon_ammo(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_weapon_ammo) }
    #[setter] fn set_on_weapon_ammo(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_weapon_ammo = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_weapon_ammo = cb.map(|c| wrap!(c, wid: u8, ammo: u16));
    }

    #[getter] fn get_on_gravity(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_gravity) }
    #[setter] fn set_on_gravity(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_gravity = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_gravity = cb.map(|c| wrap!(c, g: f32));
    }

    #[getter] fn get_on_weather(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_weather) }
    #[setter] fn set_on_weather(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_weather = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_weather = cb.map(|c| wrap!(c, w: u8));
    }

    #[getter] fn get_on_player_skin(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_skin) }
    #[setter] fn set_on_player_skin(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_skin = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_skin = cb.map(|c| wrap!(c, pid: i32, skin: u32));
    }

    #[getter] fn get_on_set_interior(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_set_interior) }
    #[setter] fn set_on_set_interior(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_set_interior = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_set_interior = cb.map(|c| wrap!(c, id: u8));
    }

    #[getter] fn get_on_vehicle_streamed_in(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_vehicle_streamed_in) }
    #[setter] fn set_on_vehicle_streamed_in(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_vehicle_streamed_in = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_vehicle_streamed_in = cb.map(|c| {
            Arc::new(move |vid: u16, model: i32, x: f32, y: f32, z: f32, angle: f32,
                           color1: u8, color2: u8, health: f32, interior: u8,
                           door_dmg: u32, panel_dmg: u32, light_dmg: u8, tire_dmg: u8,
                           add_siren: u8, paintjob: u8, bc1: u32, bc2: u32| {
                with_gil_safe(|py| {
                    use pyo3::IntoPyObject;
                    use pyo3::types::PyTuple;
                    let items: Vec<pyo3::PyObject> = vec![
                        vid.into_pyobject(py).unwrap().into_any().unbind(),
                        model.into_pyobject(py).unwrap().into_any().unbind(),
                        x.into_pyobject(py).unwrap().into_any().unbind(),
                        y.into_pyobject(py).unwrap().into_any().unbind(),
                        z.into_pyobject(py).unwrap().into_any().unbind(),
                        angle.into_pyobject(py).unwrap().into_any().unbind(),
                        color1.into_pyobject(py).unwrap().into_any().unbind(),
                        color2.into_pyobject(py).unwrap().into_any().unbind(),
                        health.into_pyobject(py).unwrap().into_any().unbind(),
                        interior.into_pyobject(py).unwrap().into_any().unbind(),
                        door_dmg.into_pyobject(py).unwrap().into_any().unbind(),
                        panel_dmg.into_pyobject(py).unwrap().into_any().unbind(),
                        light_dmg.into_pyobject(py).unwrap().into_any().unbind(),
                        tire_dmg.into_pyobject(py).unwrap().into_any().unbind(),
                        add_siren.into_pyobject(py).unwrap().into_any().unbind(),
                        paintjob.into_pyobject(py).unwrap().into_any().unbind(),
                        bc1.into_pyobject(py).unwrap().into_any().unbind(),
                        bc2.into_pyobject(py).unwrap().into_any().unbind(),
                    ];
                    let _ = c.call1(py, PyTuple::new(py, items).unwrap());
                });
            }) as Arc<dyn Fn(u16, i32, f32, f32, f32, f32, u8, u8, f32, u8, u32, u32, u8, u8, u8, u8, u32, u32) + Send + Sync>
        });
    }

    #[getter] fn get_on_vehicle_streamed_out(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_vehicle_streamed_out) }
    #[setter] fn set_on_vehicle_streamed_out(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_vehicle_streamed_out = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_vehicle_streamed_out = cb.map(|c| wrap!(c, vid: u16));
    }

    #[getter] fn get_on_player_death(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_player_death) }
    #[setter] fn set_on_player_death(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_player_death = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_player_death = cb.map(|c| wrap!(c, pid: u16));
    }

    #[getter] fn get_on_textdraw_show(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_textdraw_show) }
    #[setter] fn set_on_textdraw_show(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_textdraw_show = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_textdraw_show = cb.map(|c| {
            Arc::new(move |tid: u16, flags: u8, lw: f32, lh: f32, lcol: u32,
                           linew: f32, lineh: f32, bcol: u32, shadow: u8, outline: u8,
                           bgcol: u32, style: u8, sel: u8, x: f32, y: f32, model: u16,
                           rx: f32, ry: f32, rz: f32, zoom: f32, col1: i16, col2: i16,
                           text: String| {
                with_gil_safe(|py| {
                    use pyo3::IntoPyObject;
                    use pyo3::types::PyTuple;
                    let items: Vec<pyo3::PyObject> = vec![
                        tid.into_pyobject(py).unwrap().into_any().unbind(),
                        flags.into_pyobject(py).unwrap().into_any().unbind(),
                        lw.into_pyobject(py).unwrap().into_any().unbind(),
                        lh.into_pyobject(py).unwrap().into_any().unbind(),
                        lcol.into_pyobject(py).unwrap().into_any().unbind(),
                        linew.into_pyobject(py).unwrap().into_any().unbind(),
                        lineh.into_pyobject(py).unwrap().into_any().unbind(),
                        bcol.into_pyobject(py).unwrap().into_any().unbind(),
                        shadow.into_pyobject(py).unwrap().into_any().unbind(),
                        outline.into_pyobject(py).unwrap().into_any().unbind(),
                        bgcol.into_pyobject(py).unwrap().into_any().unbind(),
                        style.into_pyobject(py).unwrap().into_any().unbind(),
                        sel.into_pyobject(py).unwrap().into_any().unbind(),
                        x.into_pyobject(py).unwrap().into_any().unbind(),
                        y.into_pyobject(py).unwrap().into_any().unbind(),
                        model.into_pyobject(py).unwrap().into_any().unbind(),
                        rx.into_pyobject(py).unwrap().into_any().unbind(),
                        ry.into_pyobject(py).unwrap().into_any().unbind(),
                        rz.into_pyobject(py).unwrap().into_any().unbind(),
                        zoom.into_pyobject(py).unwrap().into_any().unbind(),
                        col1.into_pyobject(py).unwrap().into_any().unbind(),
                        col2.into_pyobject(py).unwrap().into_any().unbind(),
                        text.into_pyobject(py).unwrap().into_any().unbind(),
                    ];
                    let _ = c.call1(py, PyTuple::new(py, items).unwrap());
                });
            }) as Arc<dyn Fn(u16,u8,f32,f32,u32,f32,f32,u32,u8,u8,u32,u8,u8,f32,f32,u16,f32,f32,f32,f32,i16,i16,String) + Send + Sync>
        });
    }

    #[getter] fn get_on_textdraw_hide(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_textdraw_hide) }
    #[setter] fn set_on_textdraw_hide(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_textdraw_hide = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_textdraw_hide = cb.map(|c| wrap!(c, tid: u16));
    }

    #[getter] fn get_on_textdraw_edit(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_textdraw_edit) }
    #[setter] fn set_on_textdraw_edit(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_textdraw_edit = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_textdraw_edit = cb.map(|c| wrap!(c, tid: u16, text: String));
    }

    #[getter] fn get_on_textdraw_toggle_select(&self, py: Python) -> Option<Py<PyAny>> { cloned(py, &self.py_cbs.on_textdraw_toggle_select) }
    #[setter] fn set_on_textdraw_toggle_select(&mut self, py: Python, cb: Option<Py<PyAny>>) {
        self.py_cbs.on_textdraw_toggle_select = cb.as_ref().map(|c| c.clone_ref(py));
        self.inner.callbacks.lock().unwrap().on_textdraw_toggle_select = cb.map(|c| wrap!(c, enable: bool, color: u32));
    }

    fn click_textdraw(&self, textdraw_id: u16) {
        self.inner.click_textdraw(textdraw_id);
    }
}

// ── Module ────────────────────────────────────────────────────────────────────

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PySAMPClient>()?;

    // Reliability constants
    m.add("UNRELIABLE",           6u8)?;
    m.add("UNRELIABLE_SEQUENCED", 7u8)?;
    m.add("RELIABLE",             8u8)?;
    m.add("RELIABLE_ORDERED",     9u8)?;
    m.add("RELIABLE_SEQUENCED",   10u8)?;

    // Packet IDs
    m.add("ID_INTERNAL_PING",               6u8)?;
    m.add("ID_CONNECTED_PONG",              9u8)?;
    m.add("ID_CONNECTION_REQUEST",          11u8)?;
    m.add("ID_AUTH_KEY",                    12u8)?;
    m.add("ID_RPC",                         20u8)?;
    m.add("ID_OPEN_CONNECTION_REQUEST",     24u8)?;
    m.add("ID_OPEN_CONNECTION_REPLY",       25u8)?;
    m.add("ID_OPEN_CONNECTION_COOKIE",      26u8)?;
    m.add("ID_CONNECTION_ATTEMPT_FAILED",   29u8)?;
    m.add("ID_NEW_INCOMING_CONNECTION",     30u8)?;
    m.add("ID_NO_FREE_INCOMING_CONNECTIONS",31u8)?;
    m.add("ID_DISCONNECTION_NOTIFICATION",  32u8)?;
    m.add("ID_CONNECTION_LOST",             33u8)?;
    m.add("ID_CONNECTION_REQUEST_ACCEPTED", 34u8)?;
    m.add("ID_CONNECTION_BANNED",           36u8)?;
    m.add("ID_INVALID_PASSWORD",            37u8)?;

    // RPC IDs — server→client
    m.add("RPC_SERVER_JOIN",        137u8)?;
    m.add("RPC_SERVER_QUIT",        138u8)?;
    m.add("RPC_INIT_GAME",          139u8)?;
    m.add("RPC_CONNECTION_REJ",     130u8)?;
    m.add("RPC_CHAT",               101u8)?;
    m.add("RPC_CLIENT_MESSAGE",     93u8)?;
    m.add("RPC_DIALOG_BOX",         61u8)?;
    m.add("RPC_GAME_TEXT",          73u8)?;
    m.add("RPC_SET_HEALTH",         14u8)?;
    m.add("RPC_SET_ARMOUR",         66u8)?;
    m.add("RPC_SET_POSITION",       12u8)?;
    m.add("RPC_SET_CHECKPOINT",     107u8)?;
    m.add("RPC_DISABLE_CHECKPOINT", 37u8)?;
    m.add("RPC_WORLD_PLAYER_ADD",   32u8)?;
    m.add("RPC_WORLD_PLAYER_REMOVE",163u8)?;
    m.add("RPC_SET_PLAYER_NAME",    11u8)?;
    m.add("RPC_TOGGLE_CONTROLLABLE",15u8)?;
    m.add("RPC_SET_PLAYER_TIME",    29u8)?;
    m.add("RPC_SEND_DEATH_MESSAGE", 55u8)?;
    m.add("RPC_SET_ARMED_WEAPON",   67u8)?;
    m.add("RPC_SET_SPAWN_INFO",     68u8)?;
    m.add("RPC_SET_PLAYER_TEAM",    69u8)?;
    m.add("RPC_PUT_IN_VEHICLE",     70u8)?;
    m.add("RPC_REMOVE_FROM_VEHICLE",71u8)?;
    m.add("RPC_SET_PLAYER_COLOR",   72u8)?;
    m.add("RPC_SET_WORLD_TIME",     94u8)?;
    m.add("RPC_TOGGLE_SPECTATING",  124u8)?;
    m.add("RPC_SET_WANTED_LEVEL",   133u8)?;
    m.add("RPC_SET_WEAPON_AMMO",    145u8)?;
    m.add("RPC_SET_GRAVITY",        146u8)?;
    m.add("RPC_SET_WEATHER",        152u8)?;
    m.add("RPC_SET_PLAYER_SKIN",    153u8)?;
    m.add("RPC_SET_INTERIOR",       156u8)?;
    m.add("RPC_WORLD_VEHICLE_ADD",  164u8)?;
    m.add("RPC_WORLD_VEHICLE_REMOVE",165u8)?;
    m.add("RPC_DEATH_BROADCAST",    166u8)?;

    // RPC IDs — client→server
    m.add("RPC_CLIENT_JOIN",    25u8)?;
    m.add("RPC_REQUEST_CLASS",  128u8)?;
    m.add("RPC_REQUEST_SPAWN",  129u8)?;
    m.add("RPC_SPAWN",          52u8)?;
    m.add("RPC_DIALOG_RESPONSE",62u8)?;
    m.add("RPC_DEATH",          53u8)?;
    m.add("RPC_ENTER_VEHICLE",  26u8)?;
    m.add("RPC_EXIT_VEHICLE",   154u8)?;
    m.add("RPC_SERVER_COMMAND", 50u8)?;

    // TextDraw RPC IDs
    m.add("RPC_TEXTDRAW_SHOW",          134u8)?;
    m.add("RPC_TEXTDRAW_HIDE",          135u8)?;
    m.add("RPC_TEXTDRAW_EDIT",          105u8)?;
    m.add("RPC_CLICK_TEXTDRAW",         83u8)?;

    Ok(())
}
