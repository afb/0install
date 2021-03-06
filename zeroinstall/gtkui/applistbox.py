"""A GTK dialog which displays a list of Zero Install applications in the menu."""
# Copyright (C) 2009, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from zeroinstall import _
from zeroinstall.support.tasks import get_loop
import os, sys
import gtk, pango
import subprocess

from zeroinstall import support
from zeroinstall.gtkui import icon, xdgutils, gtkutils
from zeroinstall.injector import model, namespaces

gobject = get_loop().gobject

gtk2 = sys.version_info[0] < 3

def _pango_escape(s):
	return s.replace('&', '&amp;').replace('<', '&lt;')

class AppList(object):
	"""A list of applications which can be displayed in an L{AppListBox}.
	For example, a program might implement this to display a list of plugins.
	This default implementation lists applications in the freedesktop.org menus.
	"""
	def get_apps(self):
		"""Return a list of application URIs."""
		self.apps = xdgutils.discover_existing_apps()
		return self.apps.keys()

	def remove_app(self, uri):
		"""Remove this application from the list."""
		path = self.apps[uri]
		os.unlink(path)

_tooltips = {
	0: _("Run the application"),
	1: _("Show documentation files"),
	2: _("Upgrade or change versions"),
	3: _("Remove launcher from the menu"),
}

class AppListBox(object):
	"""A dialog box which lists applications already added to the menus."""
	ICON, URI, NAME, MARKUP = range(4)

	def __init__(self, iface_cache, app_list):
		"""Constructor.
		@param iface_cache: used to find extra information about programs
		@type iface_cache: L{zeroinstall.injector.iface_cache.IfaceCache}
		@param app_list: used to list or remove applications
		@type app_list: L{AppList}
		"""
		builderfile = os.path.join(os.path.dirname(__file__), 'desktop.ui')
		self.iface_cache = iface_cache
		self.app_list = app_list

		builder = gtk.Builder()
		builder.set_translation_domain('zero-install')
		builder.add_from_file(builderfile)
		self.window = builder.get_object('applist')
		tv = builder.get_object('treeview')

		self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str)

		self.populate_model()
		tv.set_model(self.model)
		tv.get_selection().set_mode(gtk.SELECTION_NONE)

		cell_icon = gtk.CellRendererPixbuf()
		cell_icon.set_property('xpad', 4)
		cell_icon.set_property('ypad', 4)
		column = gtk.TreeViewColumn('Icon', cell_icon, pixbuf = AppListBox.ICON)
		tv.append_column(column)

		cell_text = gtk.CellRendererText()
		cell_text.set_property('ellipsize', pango.ELLIPSIZE_END)
		column = gtk.TreeViewColumn('Name', cell_text, markup = AppListBox.MARKUP)
		column.set_expand(True)
		tv.append_column(column)

		cell_actions = ActionsRenderer(self, tv)
		actions_column = gtk.TreeViewColumn('Actions', cell_actions, uri = AppListBox.URI)
		tv.append_column(actions_column)

		def redraw_actions(path):
			if path is not None:
				area = tv.get_cell_area(path, actions_column)
				if gtk2:
					tv.queue_draw_area(*area)
				else:
					tv.queue_draw_area(area.x, area.y, area.width, area.height)

		tv.set_property('has-tooltip', True)
		def query_tooltip(widget, x, y, keyboard_mode, tooltip):
			x, y = tv.convert_widget_to_bin_window_coords(x, y)
			pos = tv.get_path_at_pos(x, y)
			if pos:
				new_hover = (None, None, None)
				path, col, x, y = pos
				if col == actions_column:
					area = tv.get_cell_area(path, col)
					iface = self.model[path][AppListBox.URI]
					action = cell_actions.get_action(area, x, y)
					if action is not None:
						new_hover = (path, iface, action)
				if new_hover != cell_actions.hover:
					redraw_actions(cell_actions.hover[0])
					cell_actions.hover = new_hover
					redraw_actions(cell_actions.hover[0])
				tv.set_tooltip_cell(tooltip, pos[0], pos[1], None)

				if new_hover[2] is not None:
					tooltip.set_text(_tooltips[cell_actions.hover[2]])
					return True
			return False
		tv.connect('query-tooltip', query_tooltip)

		def leave(widget, lev):
			redraw_actions(cell_actions.hover[0])
			cell_actions.hover = (None, None, None)

		tv.connect('leave-notify-event', leave)

		self.model.set_sort_column_id(AppListBox.NAME, gtk.SORT_ASCENDING)

		show_cache = builder.get_object('show_cache')
		self.window.action_area.set_child_secondary(show_cache, True)

		def response(box, resp):
			if resp == 0:	# Show Cache
				subprocess.Popen(['0store', 'manage'])
			elif resp == 1:	# Add
				from zeroinstall.gtkui.addbox import AddBox
				box = AddBox()
				box.window.connect('destroy', lambda dialog: self.populate_model())
				box.window.show()
			else:
				box.destroy()
		self.window.connect('response', response)

		# Drag-and-drop
		def uri_dropped(iface):
			if not gtkutils.sanity_check_iface(self.window, iface):
				return False
			from zeroinstall.gtkui.addbox import AddBox
			box = AddBox(iface)
			box.window.connect('destroy', lambda dialog: self.populate_model())
			box.window.show()
			return True
		gtkutils.make_iface_uri_drop_target(self.window, uri_dropped)

	def populate_model(self):
		m = self.model
		m.clear()

		for uri in self.app_list.get_apps():
			itr = m.append()
			m[itr][AppListBox.URI] = uri

			try:
				iface = self.iface_cache.get_interface(uri)
				feed = self.iface_cache.get_feed(uri)
				if feed:
					name = feed.get_name()
					summary = feed.summary or _('No information available')
					summary = summary[:1].capitalize() + summary[1:]
				else:
					name = iface.get_name()
					summary = _('No information available')
				# (GTK3 returns an extra boolean at the start)
				icon_width, icon_height = gtk.icon_size_lookup(gtk.ICON_SIZE_DIALOG)[-2:]
				pixbuf = icon.load_icon(self.iface_cache.get_icon_path(iface), icon_width, icon_height)
			except model.InvalidInterface as ex:
				name = uri
				summary = support.unicode(ex)
				pixbuf = None

			m[itr][AppListBox.NAME] = name
			if pixbuf is None:
				pixbuf = self.window.render_icon(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_DIALOG)
			m[itr][AppListBox.ICON] = pixbuf

			m[itr][AppListBox.MARKUP] = '<b>%s</b>\n<i>%s</i>' % (_pango_escape(name), _pango_escape(summary))

	def action_run(self, uri):
		feed = self.iface_cache.get_feed(uri)
		if len(feed.get_metadata(namespaces.XMLNS_IFACE, 'needs-terminal')):
			if gtk.pygtk_version >= (2,16,0) and gtk.gdk.WINDOWING == 'quartz':
				script = ['0launch', '--', uri]
				osascript = support.find_in_path('osascript')
				subprocess.Popen([osascript, '-e', 'tell app "Terminal"', '-e', 'activate',
							     '-e', 'do script "%s"' % ' '.join(script), '-e', 'end tell'])
				return
			for terminal in ['x-terminal-emulator', 'xterm', 'gnome-terminal', 'rxvt', 'konsole']:
				exe = support.find_in_path(terminal)
				if exe:
					if terminal == 'gnome-terminal':
						flag = '-x'
					else:
						flag = '-e'
					subprocess.Popen([terminal, flag, '0launch', '--', uri])
					break
			else:
				box = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, _("Can't find a suitable terminal emulator"))
				box.run()
				box.destroy()
		else:
			subprocess.Popen(['0launch', '--', uri])

	def action_help(self, uri):
		from zeroinstall.cmd import slave
		slave.invoke_master(['show-help', uri])

	def action_properties(self, uri):
		subprocess.Popen(['0launch', '--gui', '--', uri])

	def action_remove(self, uri):
		feed = self.iface_cache.get_feed(uri)
		name = feed.get_name() if feed else uri

		box = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_CANCEL, "")
		box.set_markup(_("Remove <b>%s</b> from the menu?") % _pango_escape(name))
		box.add_button(gtk.STOCK_DELETE, gtk.RESPONSE_OK)
		box.set_default_response(gtk.RESPONSE_OK)
		resp = box.run()
		box.destroy()
		if resp == gtk.RESPONSE_OK:
			try:
				self.app_list.remove_app(uri)
			except Exception as ex:
				box = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, _("Failed to remove %(interface_name)s: %(exception)s") % {'interface_name': name, 'exception': ex})
				box.run()
				box.destroy()
			self.populate_model()

class ActionsRenderer(gtk.GenericCellRenderer):
	__gproperties__ = {
		"uri": (gobject.TYPE_STRING, "Text", "Text", "-", gobject.PARAM_READWRITE),
	}

	def __init__(self, applist, widget):
		"@param widget: widget used for style information"
		gtk.GenericCellRenderer.__init__(self)
		self.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
		self.padding = 4

		self.applist = applist

		self.size = 10
		def stock_lookup(name):
			pixbuf = widget.render_icon(name, gtk.ICON_SIZE_BUTTON)
			self.size = max(self.size, pixbuf.get_width(), pixbuf.get_height())
			return pixbuf

		if hasattr(gtk, 'STOCK_MEDIA_PLAY'):
			self.run = stock_lookup(gtk.STOCK_MEDIA_PLAY)
		else:
			self.run = stock_lookup(gtk.STOCK_YES)
		self.help = stock_lookup(gtk.STOCK_HELP)
		self.properties = stock_lookup(gtk.STOCK_PROPERTIES)
		self.remove = stock_lookup(gtk.STOCK_DELETE)
		self.hover = (None, None, None)	# Path, URI, action

	def do_set_property(self, prop, value):
		setattr(self, prop.name, value)

	def do_get_size(self, widget, cell_area, layout = None):
		total_size = self.size * 2 + self.padding * 4
		return (0, 0, total_size, total_size)
	on_get_size = do_get_size		# GTK 2

	def render(self, cr, widget, background_area, cell_area, flags, expose_area = None):
		hovering = self.uri == self.hover[1]

		s = self.size

		cx = cell_area.x + self.padding
		cy = cell_area.y + (cell_area.height / 2) - s - self.padding

		ss = s + self.padding * 2

		b = 0
		for (x, y), icon in [((0, 0), self.run),
			     ((ss, 0), self.help),
			     ((0, ss), self.properties),
			     ((ss, ss), self.remove)]:
			if gtk2:
				if hovering and b == self.hover[2]:
					widget.style.paint_box(cr, gtk.STATE_NORMAL, gtk.SHADOW_OUT,
							expose_area, widget, None,
							cx + x - 2, cy + y - 2, s + 4, s + 4)

				cr.draw_pixbuf(widget.style.white_gc, icon,
						0, 0,		# Source x,y
						cx + x, cy + y)
			else:
				if hovering and b == self.hover[2]:
					gtk.render_focus(widget.get_style_context(), cr,
							cx + x - 2, cy + y - 2, s + 4, s + 4)
				gtk.gdk.cairo_set_source_pixbuf(cr, icon, cx + x, cy + y)
				cr.paint()
			b += 1

	if gtk2:
		def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
			self.render(window, widget, background_area, cell_area, flags, expose_area = expose_area)

	else:
		do_render = render

	def on_activate(self, event, widget, path, background_area, cell_area, flags):
		if event.type != gtk.gdk.BUTTON_PRESS:
			return False
		action = self.get_action(cell_area, event.x - cell_area.x, event.y - cell_area.y)
		if action == 0:
			self.applist.action_run(self.uri)
		elif action == 1:
			self.applist.action_help(self.uri)
		elif action == 2:
			self.applist.action_properties(self.uri)
		elif action == 3:
			self.applist.action_remove(self.uri)
	do_activate = on_activate

	def get_action(self, area, x, y):
		lower = int(y > (area.height / 2)) * 2

		s = self.size + self.padding * 2
		if x > s * 2:
			return None
		return int(x > s) + lower
