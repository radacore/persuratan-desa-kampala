/* ==========================================================================
   SILADESA — widget chat
   Memakai API JSON `/api/v1/chat/*`. Tanpa dependensi, tanpa build step.
   ========================================================================== */
(function () {
  "use strict";

  var API = "/api/v1";
  var KUNCI_SESI = "siladesa.sesi";
  var KUNCI_RIWAYAT = "siladesa.riwayat";

  var fab = document.getElementById("chat-fab");
  var panel = document.getElementById("chat");
  if (!fab || !panel) return;

  var badan = panel.querySelector("[data-chat-badan]");
  var form = panel.querySelector("[data-chat-form]");
  var input = panel.querySelector("[data-chat-input]");
  var kirim = panel.querySelector("[data-chat-kirim]");
  var tutup = panel.querySelector("[data-chat-tutup]");

  var sesi = sessionStorage.getItem(KUNCI_SESI);
  var sibuk = false;
  var timerSinkron = null;
  var riwayat = [];
  try {
    riwayat = JSON.parse(sessionStorage.getItem(KUNCI_RIWAYAT) || "[]");
  } catch (e) {
    riwayat = [];
  }

  function simpan() {
    try {
      sessionStorage.setItem(KUNCI_RIWAYAT, JSON.stringify(riwayat.slice(-60)));
    } catch (e) {
      /* kuota penuh: riwayat cukup di memori */
    }
  }

  function gulir() {
    badan.scrollTop = badan.scrollHeight;
  }

  // Tautan unduh (/d/…) dan halaman lacak yang dikirim bot harus bisa diklik.
  // Dibangun dengan createElement + textContent, bukan innerHTML, agar isi
  // pesan tetap tidak bisa menyuntikkan HTML.
  var POLA_TAUTAN = /(https?:\/\/[^\s]+|\/d\/[^\s]+|\/lacak\?[^\s]+)/;
  var POLA_TAUTAN_PENUH = /^(https?:\/\/[^\s]+|\/d\/[^\s]+|\/lacak\?[^\s]+)$/;

  function tambah(jenis, teks) {
    var div = document.createElement("div");
    div.className = "msg msg--" + jenis;

    var bagian = String(teks).split(POLA_TAUTAN);
    bagian.forEach(function (potong) {
      if (!potong) return;
      if (POLA_TAUTAN_PENUH.test(potong)) {
        var a = document.createElement("a");
        a.href = potong;
        a.textContent = potong;
        a.className = "msg__tautan";
        a.target = "_blank";
        a.rel = "noopener";
        div.appendChild(a);
      } else {
        div.appendChild(document.createTextNode(potong));
      }
    });

    badan.appendChild(div);
    riwayat.push({ jenis: jenis, teks: teks });
    simpan();
    gulir();
    return div;
  }

  function pilihanTombol(daftar) {
    var lama = badan.querySelector(".chat__pilihan");
    if (lama) lama.remove();
    if (!daftar || !daftar.length) return;
    var wrap = document.createElement("div");
    wrap.className = "chat__pilihan";
    daftar.forEach(function (p) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = p.label;
      b.addEventListener("click", function () {
        kirimPesan(p.value);
      });
      wrap.appendChild(b);
    });
    badan.appendChild(wrap);
    gulir();
  }

  function indikatorKetik() {
    var div = document.createElement("div");
    div.className = "chat__typing";
    div.setAttribute("data-ketik", "1");
    div.innerHTML = "<i></i><i></i><i></i>";
    div.setAttribute("aria-label", "Petugas sedang mengetik");
    badan.appendChild(div);
    gulir();
    return div;
  }

  function aktifkan(ya) {
    sibuk = !ya;
    if (kirim) kirim.disabled = !ya;
  }

  function tampilkanBalasan(data) {
    var balasan = data.balasan || [];
    balasan.forEach(function (baris) {
      tambah("bot", baris);
    });
    pilihanTombol(data.pilihan || []);
    if (data.tiket) {
      var a = document.createElement("a");
      a.className = "msg msg--sistem";
      a.href = "/lacak?tiket=" + encodeURIComponent(data.tiket);
      a.textContent = "Lihat status pengajuan " + data.tiket;
      badan.appendChild(a);
      riwayat.push({ jenis: "tautan", teks: a.textContent, href: a.getAttribute("href") });
      simpan();
      gulir();
    }
  }

  function galat(pesan) {
    tambah("sistem", pesan);
  }

  function bukaSesi() {
    return fetch(API + "/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: "web", kontak: "web-anonim" })
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        sesi = data.session_id;
        sessionStorage.setItem(KUNCI_SESI, sesi);
        (data.balasan || []).forEach(function (baris) {
          tambah("bot", baris);
        });
        pilihanTombol(data.pilihan || []);
        return data;
      });
  }

  // FR-20: pesan yang dibuat server (mis. tautan surat terbit) ikut tampil
  // walau warga tidak sedang mengetik. Server adalah sumber kebenaran.
  function sinkron() {
    if (!sesi) return Promise.resolve();
    return fetch(API + "/chat/sessions/" + encodeURIComponent(sesi) + "/messages")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var lokal = {};
        riwayat.forEach(function (item) {
          if (item.jenis === "bot") lokal[item.teks] = (lokal[item.teks] || 0) + 1;
        });
        (data.pesan || []).forEach(function (m) {
          if (m.arah !== "out") return;
          if (lokal[m.isi]) {
            lokal[m.isi] -= 1;
            return;
          }
          tambah("bot", m.isi);
        });
      })
      .catch(function () {
        /* jaringan sedang putus: coba lagi pada jadwal berikutnya */
      });
  }

  function kirimPesan(teks) {
    teks = (teks || "").trim();
    if (!teks || sibuk) return;

    tambah("user", teks);
    if (input) input.value = "";
    var lama = badan.querySelector(".chat__pilihan");
    if (lama) lama.remove();
    aktifkan(false);
    var ketik = indikatorKetik();

    var siap = sesi ? Promise.resolve() : bukaSesi();
    siap
      .then(function () {
        return fetch(API + "/chat/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sesi, pesan: teks })
        });
      })
      .then(function (r) {
        if (r.status === 404) {
          sessionStorage.removeItem(KUNCI_SESI);
          sesi = null;
          return bukaSesi().then(function () {
            return fetch(API + "/chat/messages", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_id: sesi, pesan: teks })
            });
          });
        }
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r;
      })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        ketik.remove();
        tampilkanBalasan(data);
      })
      .catch(function () {
        ketik.remove();
        galat(
          "Koneksi terputus. Periksa jaringan Anda lalu coba lagi, atau hubungi kantor desa."
        );
      })
      .then(function () {
        aktifkan(true);
        if (input) input.focus();
      });
  }

  function buka() {
    panel.setAttribute("data-buka", "1");
    fab.classList.add("sembunyi");
    fab.setAttribute("aria-expanded", "true");
    panel.setAttribute("aria-hidden", "false");
    if (riwayat.length === 0) {
      bukaSesi()
        .then(sinkron)
        .catch(function () {
          galat("Layanan chat sedang tidak dapat dihubungi. Coba beberapa saat lagi.");
        });
    } else {
      sinkron();
    }
    if (!timerSinkron) timerSinkron = setInterval(sinkron, 15000);
    if (input) setTimeout(function () { input.focus(); }, 60);
  }

  function tutupPanel() {
    if (timerSinkron) {
      clearInterval(timerSinkron);
      timerSinkron = null;
    }
    panel.setAttribute("data-buka", "0");
    panel.setAttribute("aria-hidden", "true");
    fab.classList.remove("sembunyi");
    fab.setAttribute("aria-expanded", "false");
    fab.focus();
  }

  fab.addEventListener("click", buka);
  document.querySelectorAll("[data-buka-chat]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      buka();
    });
  });
  if (tutup) tutup.addEventListener("click", tutupPanel);
  panel.addEventListener("keydown", function (e) {
    if (e.key === "Escape") tutupPanel();
  });

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      kirimPesan(input ? input.value : "");
    });
  }

  if (input) {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        kirimPesan(input.value);
      }
    });
  }

  // Pulihkan riwayat percakapan bila halaman dimuat ulang.
  riwayat.forEach(function (item) {
    if (item.jenis === "tautan") {
      var a = document.createElement("a");
      a.className = "msg msg--sistem";
      a.href = item.href;
      a.textContent = item.teks;
      badan.appendChild(a);
    } else {
      var div = document.createElement("div");
      div.className = "msg msg--" + item.jenis;
      div.textContent = item.teks;
      badan.appendChild(div);
    }
  });
  gulir();

  // Panel bisa saja sudah terbuka saat halaman dimuat (mis. dari tautan langsung).
  if (panel.getAttribute("data-buka") === "1" && sesi) {
    sinkron();
    timerSinkron = setInterval(sinkron, 15000);
  }
})();
