<%inherit file="tmBase.mak"/>


<%block name="blkHead">
<!-- tmQueryStd.blkHead: overrides tmBase.mak: blkHead -->
<script language="javascript" type="text/javascript">
function setInitialFocus() {
  // xxx using the below highlights the entire query,
  // xxx so a backspace deletes the entire query.
  //document.forma.qexpr.focus();
}
</script>
</%block>


<%block name="blkTitle"> Query </%block>


<!-- tmQueryStd.body: start -->

  <div id="form">
  <form action="" method="get" name="forma">

	<table style="border-collapse: collapse;">
	<tr>
	  <td colspan="2">
	  <input type="radio" name="qset" value="subset" ${qsetSubset}/>
		<b>At most</b> these elements, and no others <br/>
	  </td>
	</tr><tr>
	  <td colspan="2">
	  <input type="radio" name="qset" value="exact" ${qsetExact}/>
		<b>Exactly</b> these elements, in any proportions <br/>
	  </td>
	</tr><tr>
	  <td colspan="2">
	  <input type="radio" name="qset" value="superset" ${qsetSuperset}/>
		<b>At least</b> all these elements, possibly with others <br/>
	  </td>
	</tr><tr>
	  <td colspan="2">
	  <input type="radio" name="qset" value="formula" ${qsetFormula}/>
		<b>Formula:</b> exactly this chemical formula <br/>
	  </td>
	</tr>
	<tr>
	  <th class="rightAlign"> Require&nbsp;Elements: </th>
	  <td>
	  <input type="text" name="qrequires" size="30" value="${qrequires}"/>
	  </td>
	</tr>
	<tr>
	  <th class="rightAlign"> Forbid&nbsp;Elements: </th>
	  <td>
	  <input type="text" name="qforbids" size="30" value="${qforbids}"/>
	  </td>
	</tr>
	<tr>
	  <th class="rightAlign"> Restrictions: </th>
	  <td>
	  <input type="text" name="qexpr" size="80" value="${qexpr}"/>
	  </td>
	</tr>
	<tr>
	  <td class="varMapLeft">
	  <b>Variables for restrictions:</b><br>
	  The variable names for<br>
	  use in the restrictions box<br>
	  are shown to the right.
	  </td>
	  <td>
		<table>
		<tr>
		<th class="varMapRight"> Variable </th>
		<th class="varMapLeft"> Meaning </th>
		</tr>
		${varMapHtml | n}
		</table>
	  </td>
	</tr>
	</table>

    <br>
	<b>Include results from:</b>
	Stevanovic:
    % if showLastNameStevanovic:
	  <input type="checkbox" name="showLastNameStevanovic" checked="checked">
	% else:
	  <input type="checkbox" name="showLastNameStevanovic">
	% endif
	&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
	Zawadzki:
    % if showLastNameZawadzki:
	  <input type="checkbox" name="showLastNameZawadzki" checked="checked">
	% else:
	  <input type="checkbox" name="showLastNameZawadzki">
	% endif

    <br>
    % if showMinEnergyOnly:
	  <input type="checkbox" name="showMinEnergyOnly" checked="checked">
	% else:
	  <input type="checkbox" name="showMinEnergyOnly">
	% endif
	Show only the min energy row for each formula and symGroupNum
	</input>
	<br/>

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

<!-- tmQueryStd.body: end -->
