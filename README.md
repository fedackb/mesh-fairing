# **Mesh Fairing**

![fairing](https://user-images.githubusercontent.com/8960984/59396054-36e85880-8d44-11e9-873b-d8aa2293b2d5.gif)

This Blender addon provides an alternative smoothing operation. Conventional smoothing has a tendency to cause pinching, bumps, and other undesirable artifacts; however, mesh fairing results in a smooth-as-possible mesh patch.

# **Installation**

![download](https://user-images.githubusercontent.com/8960984/59553680-ab461600-8f55-11e9-8332-8f617fb40965.png)

1. Download the zip archive.

![preferences](https://user-images.githubusercontent.com/8960984/59553683-ae410680-8f55-11e9-91e9-0009257f0abb.png)

2. Install the downloaded file.

3. Enable the addon.

4. Install SciPy Python module.

	Blender ships with NumPy, but it is *highly* recommended that users install SciPy. Mesh fairing with the latter is much faster and less prone to crashing. If you encounter any issues during the automated installation process, consider attempting manual installation: https://blender.stackexchange.com/questions/56011/how-to-use-pip-with-blenders-bundled-python/56013#56013

# **Location**

Mesh fairing is available in both *Sculpt* and *Edit* modes of the *3D Viewport* panel.

![fairing-menus](https://user-images.githubusercontent.com/8960984/59396675-18379100-8d47-11e9-8146-93c5b6ba5077.png)

# **Tool Options**

Mesh fairing displaces affected vertices to produce a smooth-as-possible mesh patch with respect to a specified continuity constraint.

* **Continuity:** Determines how inner vertices blend with surrounding faces to produce a smooth-as-possible mesh patch

	* **Position:** Change in vertex position is minimized.

	* **Tangency:** Change in vertex tangency is minimized.

	* **Curvature:** Change in vertex curvature is minimized.

Mode-specific options also exist to affect the outcome of mesh fairing.

### **Sculpt Mode** ###

* **Invert Mask:** If this option is enabled, mesh fairing is applied to masked vertices; otherwise, only unmasked vertices are affected.

### **Edit Mode** ###

* **Triangulate:** Triangulates affected region to produce higher quality results

# **Usage Examples**

Here are a few examples that demonstrate the usefulness of mesh fairing:

1. Blend between sections of geometry.

	![blend](https://user-images.githubusercontent.com/8960984/59396662-09e97500-8d47-11e9-93a4-eb9d47ef007d.png)

2. Remove surface features.

	![feature-removal](https://user-images.githubusercontent.com/8960984/59397232-11aa1900-8d49-11e9-9fee-d54181dc2e0b.gif)

3. Create interesting shape keys.

	![shape-key](https://user-images.githubusercontent.com/8960984/59396649-00600d00-8d47-11e9-838d-77d3b1a06c81.gif)

# **Credits**

* **Addon Author:** Brett Fedack

* **David Model:** 3D scan of Michelangelo's David provided by [Scan the World](https://www.myminifactory.com/object/3d-print-head-of-michelangelo-s-david-52645) initiative

* **Monkey Model:** Suzanne is Blender's mascot who we've all come to know and love.

* **Other:** Special thanks to Jane Tournois whose mesh fairing implementation for [CGAL](https://github.com/CGAL/cgal/blob/master/Polygon_mesh_processing/include/CGAL/Polygon_mesh_processing/internal/fair_impl.h) proved highly instructive in designing this addon
