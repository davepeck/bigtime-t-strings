# Big Time T-Strings

The code behind https://bigtime.t-strings.help/

Big Time searches for public Python repositories that use t-strings and ranks them by how just how "BIG TIME" their usage really is.

Specifically, it:

- Uses GitHub search to find Python repositories that explicitly declare a minimum Python version of 3.14
- Further GitHub APIs to get metadata about those repositories, including star counts
- Clones each repository, parses all Python files, and walks the AST to count t-string literals ([`ast.TemplateStr`](https://docs.python.org/3/library/ast.html#ast.TemplateStr)) and imports from [`string.templatelib`](https://docs.python.org/3/library/string.templatelib.html).
- Uses a totally slapdash heuristic to rank repositories by how much they use t-strings, factoring in star counts and "density" of t-string usage
- Builds a completely goofy looking website to display the results
- Runs all of this automatically every day, in a GitHub Action

How BIG TIME are those t-strings?! We will soon find out!
