
======================
How to use annotations
======================

:Authors:
    Fabian Deutsch <fabiand@fedoraproject.org>

What are annotations?
---------------------
Annotations are a way to add annotations to a test step.
This is a bit like logging but more controlled.


How can I add an annotation?
----------------------------
Using the RESTless API and PUTing (HTTP PUT) the data to the URL
``/jobs/<cookie>/step/current/annotation``.

E.g. oVirt Node has a convenience function for this in it's common lib.


How can I retrieve annotations?
-------------------------------
Annotations are internally encoded in YAML and handled as artifacts, because
artifacts are already step specififc.
To retrieve the annotations for a specififc step just run::

  curl $IGOR_HOST/jobs/<cookie>/artifacts/0-annotations.yaml

Replace ``0`` by the step you want to retrieve the annotations for.
You can generally use::

  curl $IGOR_HOST/jobs/<cookie>/artifacts

to retrieve a list of all artifacts.

You can decode the annotations after you retrieved them using any YAML decoder.

For example in python you do::

  import yaml
  data = "<the-yaml-data>"
  list = yaml.load_all(data)
