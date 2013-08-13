<%inherit file="tmBase.mak"/>


<%block name="blkHead">
<!-- tmQueryAdv.blkHead: overrides tmBase.mak: blkHead -->
<script language="javascript" type="text/javascript">
function setInitialFocus() {
  // xxx using the below highlights the entire query,
  // xxx so a backspace deletes the entire query.
  //document.forma.qexpr.focus();
}
</script>
</%block>


<%block name="blkTitle"> Advanced Query </%block>


<!-- tmQueryAdv.body: start -->

  <div id="form">
  <form action="" method="get" name="forma">
    <table>
    <tr>
      <th>Query:</th>
      <td><input type="text" name="qexpr" size="80" value="${qexpr}"/></td>
    </tr><tr>
      <th>Sort:</th>
      <td><input type="text" name="qsort" size="80" value="${qsort}"/></td>
    </tr>
    </table>
    <input type="submit" name="submitQuery" value="Submit Query"/>
	% if len(errMsg) == 0 and len(tableHtml) > 0:
      <b>
        Total number of matches: ${numTotal}
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        Page length: ${qlimit}
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        Page:
      </b>
      % for pageName in pageNames:
        % if loop.index == currentPage:
          <input class="here" type="submit"
            name="submitQuery" value="${pageName}"/>
        % else:
          <input class="there" type="submit"
            name="submitQuery" value="${pageName}"/>
        % endif
      % endfor
    % endif
  <br/>
  </form>
  </div>

<!--
  <div style="font-size: 80%;">
  <b>Query format:</b>  Queries are Python boolean expressions using
  the column headings shown, <br>
  and the names of the elements, (H, He, Li, Be, ...) which
  represent the number of
  atoms of that element found in the chemical formula sum. <br>
  The special query "all" returns everything in the database.<br>
  A boolean expression is composed of clauses
  like:  valueA == valueB, valueA &lt; valueB, etc.,
  using the operators <span class="example"> &nbsp;&nbsp; &lt; &nbsp;&nbsp; &lt;= &nbsp;&nbsp; == &nbsp;&nbsp; != &nbsp;&nbsp; &gt;= &nbsp;&nbsp; &gt; </span><br>
  Example: &nbsp;&nbsp; <span class="example">0 &lt; bandgap &lt;= 1.5 </span><br>
  Clauses may be combined with using "and" and "or" and "not".<br>
  Example: Search for structures with a specified bandgap, and
    containing either iron or vanadium:
    &nbsp;&nbsp; <span class="example">0 &lt; bandgap &lt;= 1.5
    and (Fe &gt; 0 or V &gt; 0)</span><br>
  Standard arithmetic operators may be used.<br>
  Example: Search for structures containing copper and sulfur,
    with twice as many copper as sulfur atoms:
    &nbsp;&nbsp; <span class="example">0 &lt; Cu == 2*S</span><br>
  </div>
-->


  % if len(errMsg) == 0 and len(tableHtml) > 0:
    <p></p>
	<div id="body">
	${tableHtml | n}
	</div>
  % endif

<!-- tmQueryAdv.body: end -->
