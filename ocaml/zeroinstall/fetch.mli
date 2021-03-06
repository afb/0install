(* Copyright (C) 2013, Thomas Leonard
 * See the README file for details, or visit http://0install.net.
 *)

type fetch_feed_response =
  [ `update of (Support.Qdom.element * fetch_feed_response Lwt.t option)  (* Use this version (but a better version may come soon) *)
  | `aborted_by_user        (* Abort silently (no need to notify the user) *)
  | `problem of (string * fetch_feed_response Lwt.t option)    (* Report a problem (but may still succeed later) *)
  | `no_update ]            (* Use the previous version *)

class fetcher : General.config -> Trust.trust_db -> Downloader.downloader -> Ui.ui_handler Lazy.t ->
  object
    method download_and_import_feed : [ `remote_feed of General.feed_url ] -> fetch_feed_response Lwt.t
    method download_impls : Feed.implementation list -> [ `success | `aborted_by_user ] Lwt.t

    (** [import_feed url xml] checks the signature on [xml] and imports it into the cache if trusted.
     * If not trusted, it confirms with the user first, downloading any missing keys first. *)
    method import_feed : [`remote_feed of General.feed_url] -> string -> unit Lwt.t
    method downloader : Downloader.downloader
  end
