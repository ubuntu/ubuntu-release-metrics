# This is the 'built' branch

Do not *ever* make any manual changes in here. This is pulled by the
live deployment to deploy the charm to the actual server it runs on.

Run `charmcraft build` in a source tree, and move `build/*` here, commit all
changes, push, and run `mojo` in the production environment.